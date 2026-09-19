#!/usr/bin/env python3
"""Merge several independent handoffs into one, and see what comes back.

Stage 1 of the Continuity Programme. Each chain of handoffs loses facts, but
different chains lose *different* facts. If a model that never saw the original
document can merge several end points and recover much of what each lost
separately, then a project's memory does not live in one lineage: it lives in a
population that overlaps.

The merger sees only the handoffs, never the document, never the quiz. Its
output obeys the same word budget as its sources, so recovery cannot come from
writing more. The merged handoff is then read and graded exactly like any
other.

Refutation is as interesting as confirmation: a merger that piles up each
lineage's mistakes, or invents to reconcile them, kills the idea. Inventions are
counted separately for that reason.

Example:
  python scripts/merge_chains.py --bench experiments/PROP-EXP-MEM-008/results/clinic \\
      --quiz experiments/PROP-EXP-MEM-008/quiz-clinic.json --strategy summary \\
      --config ~/.ra-psi/run-config.json --out .../merge-summary --hop 5 --words 150
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
from evaluate_experiment import AdapterError, call, sha256_text  # noqa: E402

MERGE = """Below are {count} handover notes about the same project. They were written
independently, by systems that each saw an earlier version of it. They disagree
in coverage: each carries facts the others dropped.

Write ONE handover note that carries as much of their combined content as
possible. Keep every fact that appears in any note, with its status. Where two
notes conflict, keep the version that is more specific and say that it is
uncertain. Do not add anything that appears in none of them.

Keep the whole answer under {words} words.

"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sources(bench_dir: Path, strategy: str, hop: int) -> list[dict]:
    """The end points of every completed chain of one strategy."""
    found = []
    for path in sorted(bench_dir.glob("%s-*.json" % strategy)):
        if path.name.endswith(".failed.json") or "report" in path.name:
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        step = hb.step_at(record, hop)
        text = next((entry.get("text") for entry in record.get("chain", []) if entry.get("hop") == hop), None)
        if text and str(hop) in (record.get("grades") or {}):
            found.append({"repeat": record["repeat"], "text": text, "words": step["words_kept"],
                          "grade": record["grades"][str(hop)]})
    return found


def merge_prompt(texts: list[str], words: int) -> str:
    parts = [MERGE.format(count=len(texts), words=words)]
    for index, text in enumerate(texts, start=1):
        parts.append("=== NOTE %d ===\n%s\n\n" % (index, text.strip()))
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bench", type=Path, required=True, help="a handoff_bench output folder")
    parser.add_argument("--quiz", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--strategy", default="summary")
    parser.add_argument("--hop", type=int, default=5)
    parser.add_argument("--words", type=int, default=150)
    parser.add_argument("--merges", type=int, default=6, help="how many independent merges to run")
    parser.add_argument("--merger-model", default="openai/gpt-oss-120b")
    parser.add_argument("--reader-model", default="openai/gpt-oss-120b")
    parser.add_argument("--endpoint", default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--key", default="openrouter")
    parser.add_argument("--max-tokens", type=int, default=5000)
    args = parser.parse_args()

    private = json.loads(args.config.expanduser().read_text(encoding="utf-8"))
    location = private.get("keys", {}).get(args.key)
    if not location:
        raise SystemExit("no key location configured for %r" % args.key)
    common = {k: v for k, v in location.items() if k in ("api_key_file", "api_key_env")}
    merger = {"evaluator_id": "merger", "provider": args.key, "model": args.merger_model,
              "endpoint": args.endpoint, "json_mode": False, "max_tokens": args.max_tokens,
              "extra_body": {"reasoning": {"effort": "low"}}, **common}
    reader = {"evaluator_id": "merge-reader", "provider": args.key, "model": args.reader_model,
              "endpoint": args.endpoint, "json_mode": False, "max_tokens": args.max_tokens,
              "extra_body": {"reasoning": {"effort": "low"}}, **common}

    quiz = json.loads(args.quiz.read_text(encoding="utf-8"))
    rendered, key = hq.render_quiz(quiz, args.bench.name + ":" + quiz["quiz_version"])
    chains = sources(args.bench, args.strategy, args.hop)
    if len(chains) < 2:
        raise SystemExit("need at least two completed chains, found %d" % len(chains))

    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for index in range(1, args.merges + 1):
        stored = args.out / ("merge-%02d.json" % index)
        if stored.is_file():
            records.append(json.loads(stored.read_text(encoding="utf-8")))
            continue
        # Each merge uses every chain: the question is whether overlap repairs
        # loss, not whether a lucky subset does.
        texts = [chain["text"] for chain in chains]
        record = {"merge": index, "strategy": args.strategy, "hop": args.hop, "sources": len(texts),
                  "source_repeats": [chain["repeat"] for chain in chains], "written_at_utc": now()}
        try:
            content, _served = call(merger, merge_prompt(texts, args.words), args.max_tokens)
        except AdapterError as exc:
            record["error"] = str(exc)[:300]
            records.append(record)
            continue
        merged, cut = hb.trim(content.strip(), args.words)
        prompt = hq.reader_prompt(quiz, rendered, merged)
        try:
            answer, _served = call(reader, prompt, args.max_tokens)
        except AdapterError as exc:
            record["error"] = str(exc)[:300]
            records.append(record)
            continue
        answers, problems = hq.parse_answers(answer, [item["id"] for item in rendered])
        if not answers:
            record["error"] = "reader returned no usable answer"
            records.append(record)
            continue
        record.update(merged=merged, merged_sha256=sha256_text(merged), words=len(merged.split()),
                      trimmed=cut, problems=problems, grade=hq.grade(answers, key, rendered))
        stored.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        records.append(record)

    graded = [record for record in records if "grade" in record]
    source_accuracy = [100.0 * chain["grade"]["fact_accuracy"] for chain in chains]
    merged_accuracy = [100.0 * record["grade"]["fact_accuracy"] for record in graded]
    source_mean, source_low, source_high = hb.mean_ci(source_accuracy)
    report = {"record_version": "RA-PSI-MERGE-V1", "bench": str(args.bench), "strategy": args.strategy,
              "hop": args.hop, "word_limit": args.words, "merger": args.merger_model, "reader": args.reader_model,
              "sources": {"chains": len(chains), "mean_facts_kept_pct": round(source_mean, 1),
                          "ci95": [round(source_low, 1), round(source_high, 1)],
                          "best_single_chain_pct": round(max(source_accuracy), 1),
                          "inventions": sum(chain["grade"]["inventions"] for chain in chains)},
              "merged": {"runs": len(graded), "failed": len(records) - len(graded)}}
    if merged_accuracy:
        mean, low, high = hb.mean_ci(merged_accuracy)
        report["merged"].update({"mean_facts_kept_pct": round(mean, 1), "ci95": [round(low, 1), round(high, 1)],
                                 "inventions": sum(record["grade"]["inventions"] for record in graded),
                                 "median_words": sorted(record["words"] for record in graded)[len(graded) // 2],
                                 "recovery_pp": round(mean - source_mean, 1),
                                 "above_best_single_pp": round(mean - max(source_accuracy), 1)})
    (args.out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
