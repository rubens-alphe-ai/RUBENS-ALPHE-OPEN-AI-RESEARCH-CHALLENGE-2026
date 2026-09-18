#!/usr/bin/env python3
"""Regrade someone else's replication of a handoff-quiz experiment.

The project's largest limitation is that one generator writes every handoff and
one reader answers every quiz, because free quotas allow no more. Other agents
have models we will never afford. This script lets them run the same experiment
and send back the raw material, and it recomputes the verdict here.

What it checks, in order:

1. the submission matches `schemas/replication-submission.schema.json`;
2. it names the quiz version this repository actually froze;
3. every answer is a letter for a question of that quiz;
4. the two handoffs of a pair are different, and no handoff is reused;
5. the verdict is recomputed with the experiment's own pre-registered rule.

What it cannot check: which model really produced the text. A submission is
evidence about a method, never about an identity (ADR-003). The report states
that plainly, and the tier it assigns says what was verified here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import handoff_quiz as hq  # noqa: E402

LETTER = re.compile(r"^[A-Ea-e]$")


def load_experiment(experiment_id: str) -> tuple[dict, list[dict], dict[str, str], dict]:
    experiment = ROOT / "experiments" / experiment_id
    policy = json.loads((experiment / "evaluation_policy.json").read_text(encoding="utf-8"))
    quiz = json.loads((experiment / policy["quiz"]["file"]).read_text(encoding="utf-8"))
    rendered, key = hq.render_quiz(quiz, experiment_id + ":" + quiz["quiz_version"])
    return quiz, rendered, key, policy


def problems_in(submission: dict, quiz: dict, rendered: list[dict]) -> list[str]:
    """Structural checks that do not need a schema library."""
    found: list[str] = []
    if submission.get("submission_version") != "RA-PSI-REPLICATION-V1":
        found.append("submission_version must be RA-PSI-REPLICATION-V1")
    if submission.get("quiz_version") != quiz["quiz_version"]:
        found.append("quiz_version %r is not this experiment's %r" % (submission.get("quiz_version"), quiz["quiz_version"]))
    for role in ("generator", "reader"):
        entry = submission.get(role)
        if not isinstance(entry, dict) or not entry.get("model") or not entry.get("provider"):
            found.append("%s needs a model and a provider" % role)
    pairs = submission.get("pairs")
    if not isinstance(pairs, list) or len(pairs) < 5:
        return found + ["pairs must be a list of at least five paired trials"]
    ids = [pair.get("pair_id") for pair in pairs]
    if len(set(ids)) != len(ids):
        found.append("pair_id values must be unique")
    known = {item["id"] for item in rendered}
    seen_handoffs: dict[str, str] = {}
    for pair in pairs:
        pair_id = pair.get("pair_id", "?")
        sides = {}
        for condition in ("baseline", "structured"):
            trial = pair.get(condition)
            if not isinstance(trial, dict):
                found.append("%s: %s is missing" % (pair_id, condition))
                continue
            handoff = trial.get("handoff", "")
            answers = trial.get("answers", {})
            if not isinstance(handoff, str) or len(handoff.strip()) < 50:
                found.append("%s/%s: handoff text is missing or too short" % (pair_id, condition))
            if not isinstance(answers, dict) or not answers:
                found.append("%s/%s: no answers" % (pair_id, condition))
                continue
            unknown = sorted(set(answers) - known)
            if unknown:
                found.append("%s/%s: unknown question ids %s" % (pair_id, condition, ", ".join(unknown[:3])))
            bad = sorted(q for q, v in answers.items() if not (isinstance(v, str) and LETTER.match(v.strip())))
            if bad:
                found.append("%s/%s: answers must be one letter A-E (%s)" % (pair_id, condition, ", ".join(bad[:3])))
            digest = hashlib.sha256(handoff.strip().encode("utf-8")).hexdigest()
            if digest in seen_handoffs:
                found.append("%s/%s: same handoff text as %s" % (pair_id, condition, seen_handoffs[digest]))
            seen_handoffs[digest] = "%s/%s" % (pair_id, condition)
            sides[condition] = digest
        if len(sides) == 2 and sides["baseline"] == sides["structured"]:
            found.append("%s: both conditions have the same handoff" % pair_id)
    return found


def regrade(submission: dict, rendered: list[dict], key: dict[str, str], rule: dict) -> dict:
    pairs = []
    for pair in submission["pairs"]:
        graded = {"pair_id": pair["pair_id"]}
        for condition in ("baseline", "structured"):
            answers = {q: v.strip().upper() for q, v in pair[condition]["answers"].items()}
            graded[condition] = hq.grade(answers, key, rendered)
        pairs.append(graded)
    return hq.decide(sorted(pairs, key=lambda p: p["pair_id"]), rule)


def review(path: Path, experiment_id: str) -> dict:
    quiz, rendered, key, policy = load_experiment(experiment_id)
    submission = json.loads(path.read_text(encoding="utf-8"))
    found = problems_in(submission, quiz, rendered)
    report = {"record_version": "RA-PSI-REPLICATION-REVIEW-V1", "experiment_id": experiment_id,
              "submission_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "declared_generator": (submission.get("generator") or {}).get("model"),
              "declared_reader": (submission.get("reader") or {}).get("model"),
              "identity_note": "Model and provider are declared by the sender and cannot be verified here."}
    if found:
        report.update(status="REFUSED", problems=found[:20], evidence_tier="rejected")
        return report
    decision = regrade(submission, rendered, key, policy["quiz"])
    report.update(status="ACCEPTED", evidence_tier="reproducible_contribution",
                  pairs=len(submission["pairs"]), decision=decision["decision"],
                  reason_codes=decision["reason_codes"], summary=decision["summary"],
                  rule=policy["quiz"])
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("submission", type=Path)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--output", type=Path, help="write the review here as well")
    args = parser.parse_args()
    report = review(args.submission, args.experiment)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if report["status"] == "ACCEPTED" else 1)


if __name__ == "__main__":
    main()
