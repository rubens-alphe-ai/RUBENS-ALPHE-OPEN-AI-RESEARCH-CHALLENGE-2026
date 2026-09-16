#!/usr/bin/env python3
"""Run an experiment's independent evaluation end to end, without a human relay.

Until 2026-09-16 every scorecard reached this project through the operator:
copy a prompt into a chat, copy the JSON back, paste it into a file. That path
failed in every way it could — a file name pasted instead of its content, empty
files, a .json opened by the wrong application, the wrong chat account, a
blank Notepad — and each failure needed the operator again.

This script replaces the relay with API calls to evaluators the operator has
configured once (see evaluators.example.json):

1. **score** — send the blinded evaluator prompt to every configured scorer.
   Each call is a stateless request with no project context, which is a
   cleaner "fresh session" than a chat window can guarantee. The raw response
   is stored unchanged with its hash, the requested and the served model.
2. **ingest** — hand each response to ingest_scorecards.py, which validates it
   and joins it with the private condition map.
3. **adjudicate** — assemble the evaluation packet and run the V4 adjudicator.
4. **check** — if a critical fabrication was reported by only one scorer, send
   the disputed answers, with the exact state each was generated from, to a
   checker that did not report them, record its findings, and adjudicate again.

Independence rules are enforced, not assumed: at least two scorers from
different providers; no scorer may be the generator model; a checker may not be
an evaluator that reported the fabrication it is checking.

API keys are read from files named in the configuration at call time and are
never written anywhere. The configuration itself should live outside the
public tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from model_adapter import AdapterConfig, AdapterError, build_adapter  # noqa: E402
from ingest_scorecards import read_evaluator_json  # noqa: E402

ROOT = SCRIPTS.parent


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_config(path: Path) -> dict:
    config = json.loads(path.expanduser().read_text(encoding="utf-8"))
    for role in ("scorers", "checkers"):
        for entry in config.get(role, []):
            for field in ("evaluator_id", "provider", "model", "endpoint", "api_key_file"):
                if not entry.get(field):
                    raise SystemExit("%s entry is missing %s" % (role, field))
    return config


def independence_problems(config: dict, generation_model: str) -> list[str]:
    scorers = config.get("scorers", [])
    problems = []
    if len(scorers) < 2:
        problems.append("at least two scorers are required")
    providers = [entry["provider"].strip().lower() for entry in scorers]
    if len(set(providers)) != len(providers):
        problems.append("scorers must come from different providers")
    for entry in scorers + config.get("checkers", []):
        if entry["model"].strip().lower() == generation_model.strip().lower():
            problems.append("%s uses the generator model %s" % (entry["evaluator_id"], generation_model))
    ids = [entry["evaluator_id"] for entry in scorers + config.get("checkers", [])]
    if len(set(ids)) != len(ids):
        problems.append("evaluator_id values must be unique")
    return problems


def call(entry: dict, prompt: str, max_tokens: int) -> tuple[str, str]:
    # json_mode: forced JSON decoding. Reasoning models can spend their whole
    # budget thinking and return nothing that validates (Groq gpt-oss-120b did),
    # so it can be turned off per evaluator; the reader extracts JSON from prose.
    adapter = build_adapter(AdapterConfig(
        provider="openai-compatible", model=entry["model"], endpoint=entry["endpoint"],
        temperature=0.0, max_output_tokens=int(entry.get("max_tokens", max_tokens)), timeout_seconds=600,
        think=None, response_format="json" if entry.get("json_mode", True) else None,
        extra_body=entry.get("extra_body"), api_key_file=entry["api_key_file"]))
    content = adapter.generate(prompt, seed=1)
    return content, getattr(adapter, "last_served_model", entry["model"])


def store_raw(folder: Path, name: str, entry: dict, prompt: str, content: str, served: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    raw = folder / ("%s.raw.txt" % name)
    raw.write_text(content, encoding="utf-8")
    (folder / ("%s.metadata.json" % name)).write_text(json.dumps({
        "evaluator_id": entry["evaluator_id"], "provider": entry["provider"],
        "requested_model": entry["model"], "served_model": served,
        "endpoint_host": entry["endpoint"].split("/")[2] if "://" in entry["endpoint"] else entry["endpoint"],
        "prompt_sha256": sha256_text(prompt), "response_sha256": sha256_text(content),
        "called_at_utc": now(),
    }, indent=2) + "\n", encoding="utf-8")
    return raw


BATCH_HEADER = """# Independent evaluation request (part {part} of {parts})

You are acting ONLY as an independent evaluator. You did not produce these
answers and you must not rewrite or improve them.

{count} answers are supplied below. Each one was produced by a fresh model
session that received a project description and a fixed prompt, and was asked
to reconstruct the project's mission and state and propose a next experiment.

The answers are BLINDED and SHUFFLED. Two experimental conditions are present.
You are not told which answer belongs to which condition, and you must not try
to guess, infer or mention it. Score each answer on its own merits.

Score every answer against the rubric below, out of 100.

"""

BATCH_OUTPUT = """

## Required output

Return ONE JSON object and nothing else:
{{"evaluator_id": "<short id>", "model": "<your model>", "provider": "<provider>", "cards": [
  {{"blind_id": "BLIND-XX", "scores": {{"mission_reconstruction": 0, "current_state_fidelity": 0,
    "failure_recovery": 0, "next_action_quality": 0, "missing_information_detection": 0,
    "reproducibility": 0, "total": 0}},
    "critical_fabrications": [{{"fabrication_id": "F1", "description": "...", "evidence": "..."}}],
    "notes": "one or two sentences"}}]}}

Rules: exactly one card for each of these ids: {ids}. `total` equals the sum of
the six components; components respect the rubric maxima;
`critical_fabrications` is an empty array when you find none; never state or
speculate about which condition an answer came from.

---
"""


def build_batches(experiment: Path, pairs_per_batch: int) -> list[tuple[list[str], str]]:
    """Split the blinded answers into batches that keep each pair together.

    Free API tiers cap the tokens of a single request. When all answers cannot
    be sent at once, a batch-level shift in an evaluator's severity must not be
    able to masquerade as a treatment effect. Keeping both answers of a pair in
    the same batch makes any such shift hit both conditions of that pair
    equally, so paired deltas are unaffected. Order inside a batch is shuffled
    with a seed derived from the frozen protocol hash: reproducible, and it
    reveals nothing about conditions.
    """
    import random

    results = experiment / "results"
    packets = results / "blind_packets"
    condition_map = json.loads((results / "condition-map.private.json").read_text(encoding="utf-8"))
    manifest = json.loads((packets / "packet-manifest.json").read_text(encoding="utf-8"))
    by_pair: dict[str, list[str]] = {}
    for entry in condition_map["packets"]:
        by_pair.setdefault(entry["pair_id"], []).append(entry["blind_id"])
    pair_ids = sorted(by_pair)
    rng = random.Random(int(manifest["protocol_sha256"][:16], 16))
    rng.shuffle(pair_ids)
    rubric = (experiment / "PCRB1_SCORING.md").read_text(encoding="utf-8")
    hashes = {entry["blind_id"]: entry["output_sha256"] for entry in manifest["packets"]}
    groups = [pair_ids[i:i + pairs_per_batch] for i in range(0, len(pair_ids), pairs_per_batch)]
    batches = []
    for index, group in enumerate(groups, start=1):
        ids = [blind for pair in group for blind in by_pair[pair]]
        rng.shuffle(ids)
        parts = [BATCH_HEADER.format(part=index, parts=len(groups), count=len(ids)), rubric,
                 BATCH_OUTPUT.format(ids=", ".join(ids))]
        for blind in ids:
            text = (packets / ("%s.txt" % blind)).read_text(encoding="utf-8").strip()
            parts.append("\n## %s\n\nSHA-256: `%s`\n\n```text\n%s\n```\n" % (blind, hashes[blind], text))
        batches.append((ids, "".join(parts)))
    return batches


def score(experiment: Path, config: dict, max_tokens: int, pairs_per_batch: int = 0, batch_pause: int = 65) -> list[dict]:
    import time

    results = experiment / "results"
    api_dir = results / "api_evaluations"
    if pairs_per_batch > 0:
        batches = build_batches(experiment, pairs_per_batch)
    else:
        batches = [(None, (results / "blind_packets" / "EVALUATOR_PROMPT.md").read_text(encoding="utf-8"))]
    outcomes = []
    for entry in config["scorers"]:
        if (results / "scorecards" / ("scorecards-%s.json" % entry["evaluator_id"])).is_file():
            outcomes.append({"evaluator_id": entry["evaluator_id"], "status": "already scored"})
            continue
        cards, failure, prompt = [], None, ""
        for number, (ids, prompt) in enumerate(batches, start=1):
            if number > 1:
                time.sleep(batch_pause)  # stay under per-minute token caps
            suffix = "" if ids is None else "-batch%02d" % number
            try:
                content, served = call(entry, prompt, max_tokens)
            except AdapterError as exc:
                failure = {"status": "call failed", "batch": number, "error": str(exc)[:500]}
                break
            raw = store_raw(api_dir, entry["evaluator_id"] + suffix, entry, prompt, content, served)
            try:
                part = read_evaluator_json(raw)
            except SystemExit as exc:
                failure = {"status": "unparseable", "batch": number, "error": str(exc)}
                break
            cards.extend(part.get("cards", []))
        if failure:
            outcomes.append({"evaluator_id": entry["evaluator_id"], **failure})
            continue
        answer = {"cards": cards}
        # Identity comes from the configuration and the API response, not from
        # what the model says about itself.
        answer.update(evaluator_id=entry["evaluator_id"], provider=entry["provider"], model=served)
        normalized = api_dir / ("%s.normalized.json" % entry["evaluator_id"])
        normalized.write_text(json.dumps(answer, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ingest = subprocess.run(
            [sys.executable, str(SCRIPTS / "ingest_scorecards.py"), str(normalized),
             "--experiment", experiment.name, "--write"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        outcomes.append({"evaluator_id": entry["evaluator_id"], "served_model": served,
                         "status": "ingested" if ingest.returncode == 0 else "refused by ingestion",
                         "detail": ingest.stdout[-800:]})
    return outcomes


def adjudicate(experiment: Path) -> dict:
    scorecards_dir = experiment / "results" / "scorecards"
    if not scorecards_dir.is_dir() or not any(scorecards_dir.glob("scorecards-*.json")):
        # Nothing was ingested: report it instead of crashing on an empty folder,
        # which used to hide the providers' actual errors.
        return {"decision": "NOT_ADJUDICATED", "reason_codes": ["NO_SCORECARDS_INGESTED"]}
    cards, confirmations = [], []
    for path in sorted(scorecards_dir.glob("scorecards-*.json")):
        cards.extend(json.loads(path.read_text(encoding="utf-8")))
    for path in sorted(scorecards_dir.glob("fabrication-check-*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")).get("confirmations", []):
            confirmations.append({key: item[key] for key in ("evaluator_id", "output_sha256", "confirms_fabrication", "reasoning") if key in item})
    packet = {"packet_version": "RA-PSI-EVAL-PACKET-V4", "experiment_id": experiment.name, "stage": "pilot",
              "evaluations": cards, "fabrication_confirmations": confirmations}
    packet_path = scorecards_dir / "evaluation-packet.json"
    packet_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    decision_path = experiment / "results" / "decision.json"
    subprocess.run([sys.executable, str(SCRIPTS / "adjudicate_evaluations.py"), "--input", str(packet_path),
                    "--output", str(decision_path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(decision_path.read_text(encoding="utf-8"))


CHECK_HEADER = """# Fabrication confirmation request

You are an independent checker. You are not scoring quality and you are not
rewriting anything. You answer narrow factual questions.

Each answer below was produced by a system that received the PROJECT STATE
shown with it, then was asked to describe the project. A previous checker
claims each answer asserts as accomplished fact something that state does not
support, in a way that materially changes what a reader would believe about
the project's progress.

Confirm or reject each claim independently, using only the state shown with
that answer. Do not use outside knowledge. Its claim is an allegation to be
tested, not a finding to be ratified: do not confirm to agree with it and do
not reject to disagree with it.

"""

CHECK_OUTPUT = """
## Required output

Return ONE JSON object and nothing else:
{"findings": [{"answer_id": "BLIND-XX", "confirms_fabrication": true, "reasoning": "two sentences: what the answer asserts, what its state says"}]}
One finding per answer above.
"""


def check_fabrications(experiment: Path, config: dict, decision: dict, max_tokens: int) -> list[dict]:
    results = experiment / "results"
    summary = decision.get("score_summary", {})
    details = summary.get("details", {})
    unconfirmed = summary.get("unconfirmed_fabrication_outputs") or summary.get("disputed_fabrication_outputs") or []
    condition_map = json.loads((results / "condition-map.private.json").read_text(encoding="utf-8"))
    by_hash = {entry["output_sha256"]: entry for entry in condition_map["packets"]}
    manifest = json.loads((results / "experiment-manifest.json").read_text(encoding="utf-8"))
    state_by_trial = {trial["trial_id"]: trial["state_path"] for trial in manifest["trials"]}

    # Anyone who already voted on these outputs -- a reporting scorer or an
    # earlier checker -- is not eligible to vote again.
    already_voted = {report["evaluator_id"] for output in unconfirmed for report in details.get(output, [])}
    checkers = [entry for entry in config.get("checkers", []) if entry["evaluator_id"] not in already_voted]
    if not checkers:
        return [{"status": "no eligible checker left", "already_voted": sorted(already_voted)}]

    sections = []
    for output in unconfirmed:
        entry = by_hash[output]
        state = (ROOT / state_by_trial[entry["trial_id"]]).read_text(encoding="utf-8")
        claims = [fab.get("description", "") for report in details.get(output, []) for fab in report.get("fabrications", [])]
        answer = (results / "blind_packets" / ("%s.txt" % entry["blind_id"])).read_text(encoding="utf-8").strip()
        sections.append("## ANSWER %s\n\nAlleged fabrication: %s\n\n### State it was generated from\n\n```text\n%s\n```\n\n### Answer\n\n```text\n%s\n```\n"
                        % (entry["blind_id"], " / ".join(claims), state.strip(), answer))
    prompt = CHECK_HEADER + "\n---\n".join(sections) + CHECK_OUTPUT

    outcomes = []
    checker = checkers[0]
    try:
        content, served = call(checker, prompt, max_tokens)
    except AdapterError as exc:
        return [{"evaluator_id": checker["evaluator_id"], "status": "call failed", "error": str(exc)}]
    raw = store_raw(results / "api_evaluations", "fabrication-check-%s" % checker["evaluator_id"], checker, prompt, content, served)
    try:
        findings = read_evaluator_json(raw).get("findings", [])
    except SystemExit as exc:
        return [{"evaluator_id": checker["evaluator_id"], "status": "unparseable", "error": str(exc)}]
    blind_to_hash = {entry["blind_id"]: entry["output_sha256"] for entry in condition_map["packets"]}
    confirmations = [
        {"evaluator_id": checker["evaluator_id"], "model": served, "provider": checker["provider"],
         "blind_id": item.get("answer_id"), "output_sha256": blind_to_hash[item.get("answer_id")],
         "confirms_fabrication": bool(item.get("confirms_fabrication")), "reasoning": str(item.get("reasoning", ""))}
        for item in findings if isinstance(item, dict) and item.get("answer_id") in blind_to_hash
        and blind_to_hash[item.get("answer_id")] in unconfirmed and isinstance(item.get("confirms_fabrication"), bool)
    ]
    record = {"record_version": "RA-PSI-FABRICATION-CHECK-V1", "checked_at_utc": now(),
              "source": "API call via scripts/evaluate_experiment.py", "confirmations": confirmations,
              "limitations": ["The checker was shown the allegation it was testing, which risks anchoring."]}
    (results / "scorecards" / ("fabrication-check-%s.json" % checker["evaluator_id"])).write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    outcomes.append({"evaluator_id": checker["evaluator_id"], "served_model": served,
                     "findings_recorded": len(confirmations), "expected": len(unconfirmed)})
    return outcomes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--config", type=Path, required=True, help="evaluator configuration, kept outside the public tree")
    parser.add_argument("--max-tokens", type=int, default=8000)
    parser.add_argument("--pairs-per-batch", type=int, default=0,
                        help="score N pairs per request when a provider caps request size (0 = one request)")
    parser.add_argument("--dry-run", action="store_true", help="check configuration and independence only")
    args = parser.parse_args()

    experiment = ROOT / "experiments" / args.experiment
    config = load_config(args.config)
    manifest = json.loads((experiment / "results" / "experiment-manifest.json").read_text(encoding="utf-8"))
    generation_model = manifest.get("generation", {}).get("model", "")
    problems = independence_problems(config, generation_model)
    missing_keys = [entry["evaluator_id"] for entry in config.get("scorers", []) + config.get("checkers", [])
                    if not Path(entry["api_key_file"]).expanduser().is_file()]
    report = {"experiment": args.experiment, "generation_model": generation_model,
              "independence_problems": problems, "missing_key_files": missing_keys}
    if problems or args.dry_run or missing_keys:
        report["status"] = "REFUSED" if problems or missing_keys else "DRY_RUN_OK"
        print(json.dumps(report, indent=2, ensure_ascii=False))
        raise SystemExit(1 if problems or missing_keys else 0)

    report["scoring"] = score(experiment, config, args.max_tokens, args.pairs_per_batch)
    if args.pairs_per_batch:
        report["batching"] = {"pairs_per_batch": args.pairs_per_batch,
                              "note": "pairs kept together within a batch; record this as a protocol deviation"}
    decision = adjudicate(experiment)
    report["decision"] = decision.get("decision")
    report["reason_codes"] = decision.get("reason_codes")
    # Majority rule (owner's decision, 2026-09-16): a single report is checked;
    # a split between reporter and checker calls a second checker. Each round
    # uses a checker that has not voted yet, until the adjudicator can decide.
    pending = {"CRITICAL_FABRICATION_REQUIRES_INDEPENDENT_CONFIRMATION", "CRITICAL_FABRICATION_REQUIRES_SECOND_CHECK"}
    report["fabrication_checks"] = []
    for _ in range(len(config.get("checkers", []))):
        if not pending & set(decision.get("reason_codes") or []):
            break
        outcome = check_fabrications(experiment, config, decision, args.max_tokens)
        report["fabrication_checks"].append(outcome)
        decision = adjudicate(experiment)
        if outcome and outcome[0].get("status", "").startswith(("no eligible", "call failed", "unparseable")):
            break
    report["final_decision"] = decision.get("decision")
    report["final_reason_codes"] = decision.get("reason_codes")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
