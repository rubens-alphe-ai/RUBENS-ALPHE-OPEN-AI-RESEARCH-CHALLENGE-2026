#!/usr/bin/env python3
"""Read a run's frozen merged handoffs again, and store the answers this time.

MEM-009 published three recovery figures (+11.6, +6.9, +1.4 points) and filed,
for each merged handoff, the merged text, its SHA-256 and a `grade` — but never
the reader answers the grade was computed from, and no answer key. The numbers
are therefore not wrong and not checkable: `scripts/regression_suite.py` calls
that *unverifiable*, which is a distinct and worse category than a mismatch.

The lost answers cannot be recovered; they were never written. What survives is
the merged text, frozen and hashed. This script reads those same texts again
with a reader it names, stores the raw answers beside every grade, and writes a
report that any later run can recompute without calling a model.

What it refuses to do:

* It never writes into the run's `results/` directory. A re-reading is a new
  measurement that stands *beside* the published one, not a correction of it,
  and the unbacked numbers stay exactly as published.
* It refuses to read a merged note whose stored SHA-256 does not match its
  stored text. Re-reading an edited note would produce a number about something
  nobody published.
* It does not pretend to reproduce the original reading. The reader is recorded
  in every record and in the report; a different reader, or the same reader on a
  different day, is a different measurement and the report says so.

The source chains are a different matter: they come from MEM-008, whose records
do store their answers, so `sources` here is regraded from those answers rather
than taken on trust, and the recovery figure this script reports is a pure
function of stored letters from end to end.

Example:
  python scripts/reread_merges.py \\
      --merges experiments/PROP-EXP-MEM-009/results/clinic-summary \\
      --quiz experiments/PROP-EXP-MEM-008/quiz-clinic.json \\
      --out experiments/PROP-EXP-MEM-009/re-grading/clinic-summary \\
      --model openai/gpt-oss-120b --key openrouter --config ~/.ra-psi/run-config.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import handoff_bench as hb  # noqa: E402
import handoff_quiz as hq  # noqa: E402
import merge_chains as mc  # noqa: E402
from evaluate_experiment import AdapterError, call, sha256_text  # noqa: E402


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bench_directory(report: dict) -> Path:
    """The MEM-008 folder a merge run drew its sources from, as this OS spells it.

    `merge_chains` stores the path the way the platform that ran it rendered it,
    so a run recorded on Windows carries backslashes that POSIX would read as
    part of a filename. The separator is normalised rather than the record.
    """
    raw = str(report.get("bench", "")).replace("\\", "/")
    if not raw:
        raise SystemExit("the published report does not say which bench it merged")
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def frozen_merges(directory: Path) -> list[dict]:
    """Every merged note that was published with a grade, checked against its hash."""
    found = []
    for path in sorted(directory.glob("merge-*.json")):
        record = load(path)
        if "merged" not in record or "grade" not in record:
            continue
        if sha256_text(record["merged"]) != record.get("merged_sha256"):
            raise SystemExit("%s: the stored text does not match its stored hash; refusing to re-read it"
                             % path.name)
        found.append(record)
    return found


def regraded_sources(bench: Path, strategy: str, hop: int) -> tuple[list[float], list[str]]:
    """The source chains' fact accuracy, recomputed from MEM-008's stored answers.

    Taking the source grades as filed would make the recovery figure rest half
    on trust. MEM-008 stored the answers behind every hop, so the comparison
    baseline is recomputed; a chain whose grade no longer follows from its own
    answers is named rather than quietly averaged in.

    **The bench's own key is used, never the one the merge run rendered.** The
    two were seeded differently — `handoff_bench` seeds on "clinic.md:version",
    `merge_chains` on "clinic:version" — so the same question carries its
    options in a different order on each side. Fact accuracy does not depend on
    that order, which is why the two are comparable at all; the letters do, so
    grading one side's answers against the other side's key would turn a correct
    chain into a near-zero score and invent a recovery that never happened.
    """
    stored_key = load(bench / "answer-key.json")
    key, rendered = stored_key["key"], stored_key["rendered"]
    accuracy, moved = [], []
    for chain in mc.sources(bench, strategy, hop):
        stored = chain["grade"]
        answers = stored.get("answers")
        if answers is None:
            moved.append("repeat %d stores no answers" % chain["repeat"])
            accuracy.append(100.0 * stored["fact_accuracy"])
            continue
        again = hq.grade(answers, key, rendered)
        if any(again[field] != stored.get(field) for field in again):
            moved.append("repeat %d: stored grade differs from its own answers" % chain["repeat"])
        accuracy.append(100.0 * again["fact_accuracy"])
    return accuracy, moved


def read_one(record: dict, entry: dict, quiz: dict, rendered: list[dict],
             key: dict[str, str], out: Path) -> dict:
    """One merged note, read and stored with its answers. Resumable, never re-read."""
    stored = out / ("merge-%02d.json" % record["merge"])
    if stored.is_file():
        return load(stored)
    prompt = hq.reader_prompt(quiz, rendered, record["merged"])
    again = {"merge": record["merge"], "strategy": record["strategy"], "hop": record["hop"],
             "merged_sha256": record["merged_sha256"], "reader_id": entry["evaluator_id"],
             "reader_model": entry["model"], "read_at_utc": now(),
             "published_grade": record["grade"]}
    try:
        content, served = call(entry, prompt, int(entry.get("max_tokens", 5000)))
    except AdapterError as exc:
        again["error"] = str(exc)[:300]
        return again
    answers, problems = hq.parse_answers(content, [item["id"] for item in rendered])
    if not answers:
        again["error"] = "reader returned no usable answer"
        return again
    # answers first, grade second, and both in the same record: storing a grade
    # without the letters that produced it is the defect this run exists to end.
    again.update(served_model=served, answers=answers, problems=problems,
                 grade=hq.grade(answers, key, rendered))
    stored.write_text(json.dumps(again, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return again


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--merges", type=Path, required=True, help="a merge_chains output folder")
    parser.add_argument("--quiz", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="a folder outside the run's results/")
    parser.add_argument("--model", required=True)
    parser.add_argument("--key", required=True, help="name of the key entry in the private config")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--label", default="reread")
    parser.add_argument("--endpoint", default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--max-tokens", type=int, default=5000)
    parser.add_argument("--extra-body", default='{"reasoning": {"effort": "low"}}')
    args = parser.parse_args()

    published = load(args.merges / "report.json")
    # A re-reading that lands inside the published results/ folder would be read
    # back by the regression suite as part of the run it is meant to stand
    # beside, and would look like a correction of it. It has to live elsewhere.
    out, merges = args.out.resolve(), args.merges.resolve()
    if out == merges or merges.parent in (out, *out.parents):
        raise SystemExit("refusing to write inside %s; choose an --out outside the published results"
                         % merges.parent)

    quiz = load(args.quiz)
    bench = bench_directory(published)
    # The seed is the bench folder's name, exactly as merge_chains built it. A
    # different seed shuffles the options and silently grades against a key the
    # run never used, so the rendering is checked against the published grade.
    rendered, key = hq.render_quiz(quiz, bench.name + ":" + quiz["quiz_version"])
    merges = frozen_merges(args.merges)
    if not merges:
        raise SystemExit("no merged handoff with a grade in %s" % args.merges)
    shape = {"fact_questions": sum(1 for item in rendered if item["kind"] == "fact"),
             "absent_questions": sum(1 for item in rendered if item["kind"] == "absent")}
    for field, value in shape.items():
        if merges[0]["grade"][field] != value:
            raise SystemExit("this quiz renders %d %s but the published grade counted %d; wrong quiz or seed"
                             % (value, field, merges[0]["grade"][field]))

    private = json.loads(args.config.expanduser().read_text(encoding="utf-8"))
    location = private.get("keys", {}).get(args.key)
    if not location:
        raise SystemExit("no key location configured for %r" % args.key)
    entry = {"evaluator_id": "reread-" + args.label, "provider": args.key, "model": args.model,
             "endpoint": args.endpoint, "json_mode": False, "max_tokens": args.max_tokens,
             "extra_body": json.loads(args.extra_body),
             **{k: v for k, v in location.items() if k in ("api_key_file", "api_key_env")}}

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "answer-key.json").write_text(
        json.dumps({"key": key, "rendered": rendered, "quiz_file": str(args.quiz).replace("\\", "/"),
                    "seed_material": bench.name + ":" + quiz["quiz_version"]},
                   indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    records = [read_one(record, entry, quiz, rendered, key, args.out) for record in merges]
    graded = [record for record in records if "grade" in record]
    if not graded:
        raise SystemExit("no merged handoff could be read; nothing was written")

    accuracy = [100.0 * record["grade"]["fact_accuracy"] for record in graded]
    mean, low, high = hb.mean_ci(accuracy)
    source_accuracy, moved = regraded_sources(bench, published["strategy"], published["hop"])
    source_mean, source_low, source_high = hb.mean_ci(source_accuracy)
    report = {
        "record_version": "RA-PSI-MERGE-REREAD-V1",
        "of": str(args.merges.as_posix()),
        "status": "a new reading that stands beside the published one, not a reproduction of it",
        "reader": args.model, "reader_id": entry["evaluator_id"], "read_at_utc": now(),
        "published_reader": published.get("reader"), "merger": published.get("merger"),
        "strategy": published["strategy"], "hop": published["hop"],
        "word_limit": published.get("word_limit"),
        "sources": {"chains": len(source_accuracy), "mean_facts_kept_pct": round(source_mean, 1),
                    "ci95": [round(source_low, 1), round(source_high, 1)],
                    "best_single_chain_pct": round(max(source_accuracy), 1),
                    "regraded_from_stored_answers": not moved, "notes": moved},
        "merged": {"runs": len(graded), "failed": len(records) - len(graded),
                   "mean_facts_kept_pct": round(mean, 1), "ci95": [round(low, 1), round(high, 1)],
                   "inventions": sum(record["grade"]["inventions"] for record in graded),
                   "recovery_pp": round(mean - source_mean, 1),
                   "above_best_single_pp": round(mean - max(source_accuracy), 1)},
        "published": {"merged_mean_facts_kept_pct": published["merged"].get("mean_facts_kept_pct"),
                      "recovery_pp": published["merged"].get("recovery_pp"),
                      "above_best_single_pp": published["merged"].get("above_best_single_pp"),
                      "inventions": published["merged"].get("inventions")},
    }
    report["moved_pp"] = {
        "merged_mean": round(report["merged"]["mean_facts_kept_pct"]
                             - (report["published"]["merged_mean_facts_kept_pct"] or 0.0), 1),
        "recovery": round(report["merged"]["recovery_pp"] - (report["published"]["recovery_pp"] or 0.0), 1),
    }
    (args.out / "regrade.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
