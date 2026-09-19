#!/usr/bin/env python3
"""Replicate a handoff-quiz experiment with your own models, in one command.

Four public posts have asked other agents to replicate these results and none
has. The path we published was the problem, not the ask: clone, copy a policy
file, edit it to name your models, run a runner built for this machine's key
layout, then hand-write a JSON submission against a schema. Every one of those
steps is a place to give up.

This script is the whole path. It needs an OpenAI-compatible endpoint, a writer
model, a reader model and a file holding an API key. It runs the paired trials,
renders the quiz exactly as this repository renders it, asks the reader, grades
the letters against the key frozen before the first run, and writes a
submission that already satisfies schemas/replication-submission.schema.json.

What it refuses to do:

* It does not grade with a judge model, here or anywhere: the quiz has one
  supported answer per fact question and a "does not say" option, and grading
  is a comparison of letters (see handoff_quiz.py).
* It does not re-implement the quiz rendering. Option order is derived from the
  experiment id and the quiz version, so a replication's letters mean the same
  thing as ours; a second implementation of that shuffle would eventually drift
  and quietly invalidate every comparison.
* It does not retry in a way that hides an uneven failure rate. Only transient
  provider errors are retried, the same number of times in both conditions, and
  every failed attempt is counted and printed next to the verdict. Losses that
  fall mostly on one condition are what make a paired series worthless here, so
  they are reported, not smoothed away.
* It never reads, prints, logs or stores the API key. The adapter opens the key
  file at call time; this script only ever passes the path.
* It computes a delta for you to read, but it does not put totals in the
  submission. The receiving project regrades from the raw letters.

Example:
  python scripts/replicate.py \\
      --endpoint https://api.groq.com/openai/v1/chat/completions \\
      --writer-model llama-3.3-70b-versatile \\
      --reader-model openai/gpt-oss-120b \\
      --api-key-file ~/keys/provider.key
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import handoff_quiz as hq  # noqa: E402
from model_adapter import AdapterConfig, AdapterError, build_adapter  # noqa: E402

SUBMISSION_VERSION = "RA-PSI-REPLICATION-V1"
MIN_PAIRS = 5  # the schema's minItems; fewer is not a submission
MIN_HANDOFF_CHARS = 50  # the schema's minLength for a handoff

# Free and shared tiers answer 429 and 5xx routinely and recover within
# minutes. Those are the only errors worth asking again about; a 401, a wrong
# model id or a refused endpoint will not fix itself and stops the run at once.
TRANSIENT = ("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504", "timed out",
             "provider request failed", "rate-limited")

WHERE_TO_SEND = ("Send it back by opening an issue with the 'Replication submission' template at "
                 "https://github.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026/issues "
                 "(or a pull request adding the file under replications/).")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def call_model(endpoint: str, model: str, api_key_file: str, prompt: str, seed: int,
               temperature: float, max_tokens: int, extra_body: dict | None = None,
               timeout_seconds: int = 300) -> tuple[str, str]:
    """The only function in this file that talks to a provider.

    Everything else is deterministic, which is what lets the tests replace this
    one function and exercise the whole path without spending anything.

    The key is named, never handled: the adapter reads the file at call time and
    keeps it out of its own error messages.
    """
    adapter = build_adapter(AdapterConfig(
        provider="openai-compatible", model=model, endpoint=endpoint, temperature=temperature,
        max_output_tokens=max_tokens, timeout_seconds=timeout_seconds, think=None,
        response_format=None, extra_body=extra_body or None, api_key_file=api_key_file))
    content = adapter.generate(prompt, seed=seed)
    return content, getattr(adapter, "last_served_model", model)


def ask(stage: str, condition: str, pair_id: str, log: list[dict], retries: int, pause: float,
        **call: object) -> tuple[str, str | None]:
    """Call a model and return (text, error). Retry transient errors only.

    Every failed attempt is appended to `log` with its condition, so the run can
    report where the losses fell. A caller that receives an error has a failure
    that is already counted.
    """
    error = "no attempt was made"
    for attempt in range(retries + 1):
        try:
            content, _served = call_model(**call)  # type: ignore[arg-type]
            return content, None
        except AdapterError as exc:
            error = str(exc)[:300]
            transient = any(marker in error for marker in TRANSIENT)
            log.append({"stage": stage, "condition": condition, "pair_id": pair_id,
                        "attempt": attempt + 1, "transient": transient, "error": error})
            if not transient or attempt == retries:
                return "", error
            time.sleep(pause)
    return "", error


def read_back(prompt: str, ids: list[str], condition: str, pair_id: str, log: list[dict],
              retries: int, transient_retries: int, pause: float, **call: object) -> tuple[dict[str, str], str | None]:
    """Ask the reader for its letters, allowing a repeat of an unusable answer.

    A model that answers with prose, or with nothing this script can parse, has
    not failed transiently; it is asked again and then counted as a loss.
    Counting it is the point: a reader that fails more often on one condition
    would bias the delta in exactly the direction nobody would notice.
    """
    error = None
    for attempt in range(retries + 1):
        content, error = ask("reader", condition, pair_id, log, transient_retries, pause, prompt=prompt, **call)
        if error is not None:
            # ask() has already exhausted the transient retries; anything still
            # failing here will keep failing, so stop and let it be counted.
            return {}, error
        answers, problems = hq.parse_answers(content, ids)
        if answers:
            return answers, None
        error = "reader returned no usable letters (%s)" % ("; ".join(problems[:2]) or "empty answer")
        log.append({"stage": "reader", "condition": condition, "pair_id": pair_id,
                    "attempt": attempt + 1, "transient": False, "error": error})
        if attempt < retries:
            time.sleep(pause)
    return {}, error


def load_experiment(experiment_id: str) -> dict:
    """Read the frozen inputs of an experiment; refuse anything incomplete.

    A replicator who mistypes an experiment id, or points this at a directory
    that was never a quiz experiment, should be told which file is missing
    rather than watch a traceback.
    """
    folder = ROOT / "experiments" / experiment_id
    policy_path = folder / "evaluation_policy.json"
    if not policy_path.is_file():
        raise SystemExit("no experiment %r: %s does not exist" % (experiment_id, policy_path))
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    generation = policy.get("generation") or {}
    quiz_cfg = policy.get("quiz") or {}
    missing = [name for name in ("baseline_state", "structured_state", "seeds") if not generation.get(name)]
    if missing or not quiz_cfg.get("file"):
        raise SystemExit("%s is not a runnable handoff-quiz policy (missing %s)"
                         % (policy_path, ", ".join(missing + ([] if quiz_cfg.get("file") else ["quiz.file"]))))
    paths = {"baseline": folder / generation["baseline_state"], "structured": folder / generation["structured_state"],
             "prompt": folder / "TEST_PROMPT.md", "quiz": folder / quiz_cfg["file"]}
    absent = sorted(str(path) for path in paths.values() if not path.is_file())
    if absent:
        raise SystemExit("experiment %s is missing: %s" % (experiment_id, ", ".join(absent)))
    quiz = json.loads(paths["quiz"].read_text(encoding="utf-8"))
    rendered, key = hq.render_quiz(quiz, experiment_id + ":" + quiz["quiz_version"])
    return {"experiment_id": experiment_id, "policy": policy, "quiz": quiz, "rendered": rendered, "key": key,
            "rule": quiz_cfg, "generation": generation,
            "states": {"baseline": paths["baseline"].read_text(encoding="utf-8"),
                       "structured": paths["structured"].read_text(encoding="utf-8")},
            "test_prompt": paths["prompt"].read_text(encoding="utf-8")}


def seeds_for(generation: dict, pairs: int) -> list[int]:
    """The experiment's own seeds first, so a short run repeats our first pairs."""
    frozen = [int(seed) for seed in generation.get("seeds", [])]
    while len(frozen) < pairs:
        frozen.append((max(frozen) if frozen else 0) + 1)
    return frozen[:pairs]


def provider_from(endpoint: str) -> str:
    """A declared label for the submission, taken from the endpoint's host.

    Nothing here verifies a provider any more than it verifies a model; the
    receiving project records both as declared (ADR-003).
    """
    if "://" in endpoint:
        host = endpoint.split("://", 1)[1].split("/", 1)[0]
        if host:
            return host
    return endpoint or "unknown"


def run(options: argparse.Namespace) -> dict:
    experiment = load_experiment(options.experiment)
    ids = [item["id"] for item in experiment["rendered"]]
    key_file = Path(options.api_key_file).expanduser()
    # Existence and size only. Reading the file here would put the key in this
    # process for no reason; the adapter needs it and this script does not.
    if not key_file.is_file():
        raise SystemExit("no API key file at %s; write your key into that file (one line) and run again" % key_file)
    if key_file.stat().st_size == 0:
        raise SystemExit("the API key file %s is empty" % key_file)
    if options.pairs < 1:
        raise SystemExit("--pairs must be at least 1")

    generation = experiment["generation"]
    temperature = options.temperature if options.temperature is not None else float(generation.get("temperature", 0.8))
    writer_tokens = options.writer_max_tokens or int(generation.get("max_output_tokens", 1000))
    reader_tokens = options.reader_max_tokens or int((experiment["policy"].get("reader") or {}).get("max_tokens", 1500))
    extra_body = json.loads(options.extra_body) if options.extra_body else None
    if extra_body is not None and not isinstance(extra_body, dict):
        raise SystemExit("--extra-body must be a JSON object, for example '{\"reasoning_effort\": \"low\"}'")
    seeds = seeds_for(generation, options.pairs)

    print("experiment %s, %d pairs, seeds %s" % (options.experiment, options.pairs,
                                                 ", ".join(str(seed) for seed in seeds)), flush=True)
    print("writer %s at %s (temperature %s), reader %s" % (options.writer_model, provider_from(options.endpoint),
                                                           temperature, options.reader_model), flush=True)
    if options.writer_model.strip().lower() == options.reader_model.strip().lower():
        # The whole design rests on the reader being a different model: one that
        # shares no context with the writer and cannot recognise its own prose.
        print("warning: the writer and the reader are the same model. This experiment asks a different model to "
              "read the handoff; a same-model run measures something else, so say so when you send it", flush=True)
    if temperature == 0:
        # Identical handoffs across pairs are refused by validate_replication.py,
        # and a greedy writer is the usual way to produce them.
        print("warning: at temperature 0 every pair may produce the same handoff, "
              "and identical handoffs are refused on arrival", flush=True)
    if options.dry_run:
        print("dry run: no model was called", flush=True)
        return {"status": "DRY_RUN", "pairs": [], "log": [], "lost": {}}

    log: list[dict] = []
    lost = {"baseline": 0, "structured": 0}
    pairs: list[dict] = []
    for index, seed in enumerate(seeds, start=1):
        pair_id = "pair-%02d" % index
        sides: dict[str, dict] = {}
        for condition in ("baseline", "structured"):
            # Fresh, stateless request each time: nothing from the other
            # condition, the other pair or the quiz reaches the writer.
            writer_prompt = experiment["states"][condition] + "\n\n" + experiment["test_prompt"]
            handoff, error = ask("writer", condition, pair_id, log, options.retries, options.pause,
                                 endpoint=options.endpoint, model=options.writer_model,
                                 api_key_file=str(key_file), prompt=writer_prompt, seed=seed,
                                 temperature=temperature, max_tokens=writer_tokens, extra_body=extra_body,
                                 timeout_seconds=options.timeout)
            if error is not None:
                print("%s/%s: writer failed: %s" % (pair_id, condition, error), flush=True)
                lost[condition] += 1
                break
            handoff = handoff.strip()
            if len(handoff) < MIN_HANDOFF_CHARS:
                error = "writer returned %d characters; a handoff must be at least %d" % (len(handoff), MIN_HANDOFF_CHARS)
                log.append({"stage": "writer", "condition": condition, "pair_id": pair_id,
                            "attempt": 1, "transient": False, "error": error})
                print("%s/%s: %s" % (pair_id, condition, error), flush=True)
                lost[condition] += 1
                break
            answers, error = read_back(hq.reader_prompt(experiment["quiz"], experiment["rendered"], handoff), ids,
                                       condition, pair_id, log, options.reader_retries, options.retries, options.pause,
                                       endpoint=options.endpoint, model=options.reader_model,
                                       api_key_file=str(key_file), seed=seed, temperature=0.0,
                                       max_tokens=reader_tokens, extra_body=extra_body,
                                       timeout_seconds=options.timeout)
            if error is not None:
                print("%s/%s: %s" % (pair_id, condition, error), flush=True)
                lost[condition] += 1
                break
            sides[condition] = {"handoff": handoff, "answers": answers}
        if len(sides) == 2:
            pairs.append({"pair_id": pair_id, "seed": seed, "baseline": sides["baseline"],
                          "structured": sides["structured"]})
            graded = {c: hq.grade(sides[c]["answers"], experiment["key"], experiment["rendered"])
                      for c in ("baseline", "structured")}
            print("%s: fact accuracy %.1f%% -> %.1f%%, inventions %d -> %d"
                  % (pair_id, 100 * graded["baseline"]["fact_accuracy"], 100 * graded["structured"]["fact_accuracy"],
                     graded["baseline"]["inventions"], graded["structured"]["inventions"]), flush=True)
        else:
            print("%s: dropped, a pair needs both conditions" % pair_id, flush=True)
    return {"status": "RAN", "pairs": pairs, "log": log, "lost": lost, "experiment": experiment,
            "temperature": temperature, "writer_tokens": writer_tokens, "reader_tokens": reader_tokens}


def duplicate_handoffs(pairs: list[dict]) -> list[str]:
    """Handoffs that repeat. validate_replication.py refuses a submission that has any."""
    seen: dict[str, str] = {}
    repeats = []
    for pair in pairs:
        for condition in ("baseline", "structured"):
            digest = hashlib.sha256(pair[condition]["handoff"].strip().encode("utf-8")).hexdigest()
            where = "%s/%s" % (pair["pair_id"], condition)
            if digest in seen:
                repeats.append("%s repeats %s" % (where, seen[digest]))
            seen[digest] = where
    return repeats


def build_submission(outcome: dict, options: argparse.Namespace) -> dict:
    experiment = outcome["experiment"]
    provider = options.provider or provider_from(options.endpoint)
    attempts = len(outcome["log"])
    notes = ["Produced by scripts/replicate.py on %s." % now(),
             "Requested %d pairs; %d complete." % (options.pairs, len(outcome["pairs"])),
             "Pairs lost: %d in baseline, %d in structured." % (outcome["lost"]["baseline"], outcome["lost"]["structured"]),
             "%d failed model attempts were recorded across both conditions." % attempts,
             "No totals are included here; the letters are raw and meant to be regraded."]
    if options.notes:
        notes.append(options.notes.strip())
    submission = {
        "submission_version": SUBMISSION_VERSION,
        "experiment_id": experiment["experiment_id"],
        "quiz_version": experiment["quiz"]["quiz_version"],
        "generator": {"model": options.writer_model, "provider": provider, "temperature": outcome["temperature"],
                      "max_output_tokens": outcome["writer_tokens"],
                      "note": "declared by the replicator; not verified by this script"},
        "reader": {"model": options.reader_model, "provider": provider, "temperature": 0.0,
                   "max_output_tokens": outcome["reader_tokens"],
                   "note": "declared by the replicator; not verified by this script"},
        "notes": " ".join(notes)[:4000],
        "pairs": outcome["pairs"],
    }
    if options.submitted_by:
        submission["submitted_by"] = options.submitted_by
    return submission


def write_submission(outcome: dict, options: argparse.Namespace) -> tuple[Path, bool]:
    """Write the submission and say whether it is one.

    A run that lost too many pairs still has work worth keeping, so it is
    written; but it is written under a name that says what it is, because a
    file this project would refuse must never be mistaken for one it would
    accept.
    """
    complete = len(outcome["pairs"]) >= MIN_PAIRS
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = options.out or (ROOT / "replications" / ("replication-%s-%s.json" % (options.experiment, stamp)))
    path = Path(path)
    if not complete:
        path = path.with_name(path.stem + ".incomplete" + path.suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_submission(outcome, options), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path, complete


def report(outcome: dict, path: Path, complete: bool) -> None:
    """Print the delta, its interval, the inventions and where the losses fell."""
    experiment = outcome["experiment"]
    graded = [{"pair_id": pair["pair_id"],
               **{c: hq.grade(pair[c]["answers"], experiment["key"], experiment["rendered"])
                  for c in ("baseline", "structured")}}
              for pair in outcome["pairs"]]
    decision = hq.decide(sorted(graded, key=lambda p: p["pair_id"]), experiment["rule"])
    summary = decision["summary"]
    print("")
    print("pairs completed: %d" % summary["pairs"])
    if "mean_paired_delta_pp" in summary:
        low, high = summary["ci95_delta_pp"]
        print("paired delta (treatment minus baseline): %+.1f pp, 95%% CI [%+.1f, %+.1f]"
              % (summary["mean_paired_delta_pp"], low, high))
        print("inventions: %d in baseline, %d in structured"
              % (summary["inventions"]["baseline"], summary["inventions"]["structured"]))
        print("this run's own verdict under the experiment's frozen rule: %s %s"
              % (decision["decision"], decision["reason_codes"] or ""))
    else:
        print("too few pairs to compute a delta")

    failures = outcome["log"]
    if failures:
        by_condition = {c: sum(1 for item in failures if item["condition"] == c) for c in ("baseline", "structured")}
        print("")
        print("failed model attempts: %d in baseline, %d in structured"
              % (by_condition["baseline"], by_condition["structured"]))
        print("pairs lost: %d in baseline, %d in structured"
              % (outcome["lost"]["baseline"], outcome["lost"]["structured"]))
        if outcome["lost"]["baseline"] != outcome["lost"]["structured"]:
            # This is the failure mode that quietly invalidates a paired series:
            # if one condition loses more trials than the other, the surviving
            # pairs are no longer a fair comparison.
            print("WARNING: the losses are uneven across conditions. A series that loses more trials in one "
                  "condition than the other is not evidence here. Rerun, or say so when you send this.")
        for item in failures[:5]:
            print("  %s %s %s attempt %d: %s" % (item["pair_id"], item["condition"], item["stage"],
                                                 item["attempt"], item["error"][:160]))
        if len(failures) > 5:
            print("  ... and %d more" % (len(failures) - 5))

    repeats = duplicate_handoffs(outcome["pairs"])
    if repeats:
        print("")
        print("WARNING: identical handoffs are refused on arrival: %s" % "; ".join(repeats[:3]))
        print("Raise the writer's temperature and run again.")

    print("")
    if complete:
        print("submission written to: %s" % path)
        print(WHERE_TO_SEND)
    else:
        print("INCOMPLETE: %d complete pairs, and a submission needs %d." % (len(outcome["pairs"]), MIN_PAIRS))
        print("The work that did succeed is in: %s" % path)
        print("That file does not satisfy the schema and should not be sent as it stands.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--endpoint", required=True, help="an OpenAI-compatible /chat/completions URL")
    parser.add_argument("--writer-model", required=True, help="the model that reads the state and writes the handoff")
    parser.add_argument("--reader-model", required=True,
                        help="the model that sees only the handoff and answers the quiz; use a different model")
    parser.add_argument("--api-key-file", required=True,
                        help="path to a file containing the API key. It is read by the adapter at call time "
                             "and is never printed, logged or copied into the submission")
    parser.add_argument("--experiment", default="PROP-EXP-MEM-005")
    parser.add_argument("--pairs", type=int, default=MIN_PAIRS,
                        help="paired trials to run (default %d, the fewest a submission may carry; "
                             "this project ran 30). Each pair is 4 model calls" % MIN_PAIRS)
    parser.add_argument("--out", type=Path, help="where to write the submission "
                                                 "(default: replications/replication-<experiment>-<timestamp>.json)")
    parser.add_argument("--provider", help="provider label for the submission (default: the endpoint's host)")
    parser.add_argument("--submitted-by", help="any handle; unverifiable, and never used to weigh the evidence")
    parser.add_argument("--notes", help="anything the receiving project should know about this run")
    parser.add_argument("--temperature", type=float, help="writer temperature (default: the experiment's own)")
    parser.add_argument("--writer-max-tokens", type=int, help="default: the experiment's own")
    parser.add_argument("--reader-max-tokens", type=int, help="default: the experiment's own")
    parser.add_argument("--extra-body", help='provider-specific request fields as JSON, applied to both models, '
                                             'for example \'{"reasoning_effort": "low"}\'')
    parser.add_argument("--retries", type=int, default=2,
                        help="retries for transient provider errors only, per call, identical in both conditions")
    parser.add_argument("--reader-retries", type=int, default=1, help="repeats allowed for an unusable reader answer")
    parser.add_argument("--pause", type=float, default=20.0, help="seconds to wait before a retry")
    parser.add_argument("--timeout", type=int, default=300, help="seconds to wait for one response")
    parser.add_argument("--dry-run", action="store_true", help="check the inputs and the key file, call nothing")
    options = parser.parse_args()

    outcome = run(options)
    if outcome["status"] == "DRY_RUN":
        raise SystemExit(0)

    path, complete = write_submission(outcome, options)
    report(outcome, path, complete)
    raise SystemExit(0 if complete else 2)


if __name__ == "__main__":
    main()
