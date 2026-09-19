#!/usr/bin/env python3
"""Compare handoff strategies on any document, and say which one loses least.

The experiments so far answered one question at a time: does this format help?
The useful product is the comparison: given *your* document, which way of
passing it on keeps the most facts, and how fast does it decay when it is passed
again, and again?

For each strategy, the generator writes a handoff from the document. Optionally
the handoff is passed on for several hops, each writer seeing only what the
previous one wrote — which is what actually happens across sessions and models.
At the end a reader that never saw the document answers a quiz whose answers
were fixed beforehand (`build_quiz_from_document.py`), and a script grades the
letters. Nothing is judged by a model.

Reported per strategy: facts kept, facts invented, the paired difference against
the control strategy, and the cost.

Example:
  python scripts/handoff_bench.py --document notes.md --quiz quiz.json \\
      --config ~/.ra-psi/run-config.json --out bench/ --repeats 5 --hops 1
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import handoff_quiz as hq  # noqa: E402
from evaluate_experiment import AdapterError, call, sha256_text  # noqa: E402

INSTRUCTIONS = {
    "summary": "Summarise the text above for whoever takes this over.",
    "checklist": ("Write a handover for whoever takes this over. Carry over as many distinct facts as possible, "
                  "each with its status: what is established, what was decided and why, what failed and how it was "
                  "fixed, what is planned, what is still open, and the rules in force. Prefer short factual "
                  "statements over commentary."),
    "sections": ("Write a handover for whoever takes this over, as named sections with a short heading per theme and "
                 "one fact per line."),
    "facts_only": ("List the facts of the text above, one per line, each a complete sentence that can be understood "
                   "alone. No introduction, no conclusion, no commentary."),
}


def strategies(words: int) -> dict:
    """The same length limit for every strategy: the format is the variable."""
    limit = " Keep the whole answer under %d words." % words
    return {name: text + limit for name, text in INSTRUCTIONS.items()}


STRATEGIES = strategies(450)

CONTROL = "summary"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def trim(text: str, words: int | None) -> tuple[str, bool]:
    """Cut a handoff to the allowed length, the same way for every strategy.

    A strategy that ignores the word limit keeps more facts because it wrote
    more, not because its format is better. Cutting every handoff to the same
    number of words removes that advantage mechanically instead of trusting the
    writer to obey.
    """
    if not words:
        return text, False
    parts = text.split()
    if len(parts) <= words:
        return text, False
    return " ".join(parts[:words]), True


def write_chain(entry: dict, source: str, instruction: str, hops: int, max_tokens: int,
                words: int | None, attempts: int = 2) -> list[dict]:
    """One handoff per hop; each hop sees only the previous, trimmed, handoff."""
    chain = []
    current = source
    for hop in range(1, hops + 1):
        prompt = current + "\n\n" + instruction
        last: AdapterError | None = None
        for _ in range(attempts):
            try:
                content, _served = call(entry, prompt, max_tokens)
                break
            except AdapterError as exc:
                last = exc
        else:
            raise last or AdapterError("no answer")
        text, cut = trim(content.strip(), words)
        chain.append({"hop": hop, "text": text, "words_written": len(content.split()),
                      "words_kept": len(text.split()), "trimmed": cut, "sha256": sha256_text(text)})
        current = text
    return chain


def mean_ci(values: list[float]) -> tuple[float, float, float]:
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, mean, mean
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    half = hq.T_975.get(n - 1, 1.96) * sd / math.sqrt(n)
    return mean, mean - half, mean + half


def run_case(case: dict, document: str, quiz: dict, rendered: list[dict], key: dict[str, str],
             generator: dict, reader: dict, read_at: list[int], max_tokens: int, out: Path,
             words: int | None = None) -> dict:
    name, repeat = case["strategy"], case["repeat"]
    stored = out / ("%s-%02d.json" % (name, repeat))
    if stored.is_file():
        return json.loads(stored.read_text(encoding="utf-8"))
    record = {"strategy": name, "repeat": repeat, "read_at": read_at, "word_limit": words,
              "written_at_utc": now()}

    def failed(reason: str) -> dict:
        # A failure is written down too: a silent one could quietly remove the
        # runs where a strategy struggles, which is exactly the runs that matter.
        record["error"] = reason[:300]
        (out / ("%s-%02d.failed.json" % (name, repeat))).write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return record

    try:
        chain = write_chain(generator, document, case["instruction"], max(read_at), max_tokens, words)
    except AdapterError as exc:
        return failed(str(exc))
    record["chain"] = chain
    grades = {}
    for hop in read_at:
        handoff = chain[hop - 1]["text"]
        prompt = hq.reader_prompt(quiz, rendered, handoff)
        try:
            content, _served = call(reader, prompt, int(reader.get("max_tokens", 2000)))
        except AdapterError as exc:
            return failed("hop %d: %s" % (hop, exc))
        answers, problems = hq.parse_answers(content, [item["id"] for item in rendered])
        if not answers:
            return failed("hop %d: reader returned no usable answer" % hop)
        grades[str(hop)] = {"answers": answers, "problems": problems,
                            **hq.grade(answers, key, rendered)}
    record["grades"] = grades
    stored.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def step_at(record: dict, hop: int) -> dict:
    """The chain step written at that depth, found by its hop number."""
    for step in record.get("chain", []):
        if step.get("hop") == hop:
            return step
    return {"words_kept": 0, "trimmed": False}


def summarise(records: list[dict], hop: int, control: str = CONTROL) -> dict:
    """Per strategy, at one depth of the chain, each compared to the control arm."""
    key = str(hop)
    by_strategy: dict[str, list[dict]] = {}
    for record in records:
        if key in (record.get("grades") or {}):
            by_strategy.setdefault(record["strategy"], []).append(record)
    table = {}
    for name, rows in by_strategy.items():
        accuracy = [100.0 * row["grades"][key]["fact_accuracy"] for row in rows]
        mean, low, high = mean_ci(accuracy)
        table[name] = {"runs": len(rows), "facts_kept_pct": round(mean, 1),
                       "ci95": [round(low, 1), round(high, 1)],
                       "inventions": sum(row["grades"][key]["inventions"] for row in rows),
                       "absent_questions_asked": sum(row["grades"][key]["absent_questions"] for row in rows),
                       "median_words": sorted(step_at(row, hop)["words_kept"] for row in rows)[len(rows) // 2],
                       "trimmed_runs": sum(1 for row in rows if step_at(row, hop)["trimmed"])}
    baseline = table.get(control)
    for name, row in table.items():
        if baseline and name != control:
            paired = [100.0 * (a["grades"][key]["fact_accuracy"] - b["grades"][key]["fact_accuracy"])
                      for a, b in zip(by_strategy[name], by_strategy[control])]
            mean, low, high = mean_ci(paired)
            row["vs_control_pp"] = round(mean, 1)
            row["vs_control_ci95"] = [round(low, 1), round(high, 1)]
    return table


def render_report(tables: dict, meta: dict, control: str = CONTROL) -> str:
    """One table per depth of the chain, so the decay is visible, not averaged."""
    lines = ["# Handoff benchmark", "",
             "Document: `%s` — %d fact questions, %d absent-fact questions, %d runs per strategy, "
             "handoffs cut to %s words."
             % (meta["document"], meta["fact_questions"], meta["absent_questions"], meta["repeats"],
                meta.get("word_limit") or "no limit"),
             "Writer: `%s`. Reader: `%s`. Grading compares letters to a key fixed before the run; no model scores anything."
             % (meta["generator"], meta["reader"]), ""]
    for hop in sorted(tables, key=int):
        table = tables[hop]
        lines += ["## After %s handoff(s)" % hop, "",
                  "| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |",
                  "|---|---|---|---|---|---|---|"]
        for name in sorted(table, key=lambda n: -table[n]["facts_kept_pct"]):
            row = table[name]
            against = "control" if name == control else "%+.1f pp (%.1f to %.1f)" % (
                row.get("vs_control_pp", 0), *row.get("vs_control_ci95", (0, 0)))
            lines.append("| %s | %.1f%% | %.1f to %.1f | %s | %d of %d | %d | %d of %d |" % (
                name, row["facts_kept_pct"], row["ci95"][0], row["ci95"][1], against,
                row["inventions"], row["absent_questions_asked"], row["median_words"],
                row["trimmed_runs"], row["runs"]))
        lines.append("")
    lines += ["Facts kept: share of questions the reader answered correctly from the handoff alone.",
              "Invented: answers given to questions the document never answered.",
              "Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.",
              "Every handoff, every answer and the key are stored next to this report, so any of it can be regraded."]
    if meta.get("failed_runs"):
        lines.append("Failed runs, excluded and listed in report.json: %d." % meta["failed_runs"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--quiz", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--read-at", type=int, nargs="+", default=[1],
                        help="depths of the chain to measure, e.g. 1 3 5")
    parser.add_argument("--words", type=int, default=450,
                        help="length limit given to every strategy; handoffs longer than this are cut")
    parser.add_argument("--strategies", nargs="*", default=sorted(STRATEGIES))
    parser.add_argument("--generator-model", default="deepseek/deepseek-v4.1-flash")
    parser.add_argument("--reader-model", default="openai/gpt-oss-120b")
    parser.add_argument("--endpoint", default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--key", default="openrouter")
    parser.add_argument("--max-tokens", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    private = json.loads(args.config.expanduser().read_text(encoding="utf-8"))
    location = private.get("keys", {}).get(args.key)
    if not location:
        raise SystemExit("no key location configured for %r" % args.key)
    common = {k: v for k, v in location.items() if k in ("api_key_file", "api_key_env")}
    generator = {"evaluator_id": "bench-writer", "provider": args.key, "model": args.generator_model,
                 "endpoint": args.endpoint, "json_mode": False, "max_tokens": args.max_tokens,
                 "extra_body": {"reasoning": {"enabled": False}}, **common}
    reader = {"evaluator_id": "bench-reader", "provider": args.key, "model": args.reader_model,
              "endpoint": args.endpoint, "json_mode": False, "max_tokens": 2000,
              "extra_body": {"reasoning": {"effort": "low"}}, **common}

    document = args.document.read_text(encoding="utf-8")
    quiz = json.loads(args.quiz.read_text(encoding="utf-8"))
    rendered, key = hq.render_quiz(quiz, args.document.name + ":" + quiz["quiz_version"])
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "answer-key.json").write_text(json.dumps({"key": key, "rendered": rendered}, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")

    chosen = strategies(args.words)
    cases = [{"strategy": name, "repeat": index, "instruction": chosen[name]}
             for name in args.strategies for index in range(1, args.repeats + 1)]
    read_at = sorted(set(args.read_at))
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        records = list(pool.map(lambda case: run_case(case, document, quiz, rendered, key, generator, reader,
                                                      read_at, args.max_tokens, args.out, args.words), cases))
    failed = [record for record in records if "grades" not in record]
    tables = {str(hop): summarise(records, hop) for hop in read_at}
    meta = {"document": args.document.name, "fact_questions": sum(1 for item in rendered if item["kind"] == "fact"),
            "absent_questions": sum(1 for item in rendered if item["kind"] == "absent"), "read_at": read_at,
            "repeats": args.repeats, "generator": args.generator_model, "reader": args.reader_model,
            "word_limit": args.words, "failed_runs": len(failed),
            "failures": [{"strategy": row["strategy"], "repeat": row["repeat"], "error": row.get("error", "")[:160]}
                         for row in failed]}
    (args.out / "report.json").write_text(json.dumps({"meta": meta, "by_hop": tables}, indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    (args.out / "report.md").write_text(render_report(tables, meta), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "failed_runs": len(failed), "by_hop": tables}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
