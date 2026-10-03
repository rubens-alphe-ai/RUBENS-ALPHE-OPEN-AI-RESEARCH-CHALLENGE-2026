#!/usr/bin/env python3
"""Replicate the defect diagnosis on questions the diagnosing model cannot have seen.

DIAGNOSIS-REDUX-2026-10 found that deepseek-v4.1-flash, blind to the flag,
sorts flagged MMLU items by probable defect. Its stated limit: MMLU and the
MMLU-Redux annotations are public, so the model may have memorised the items
or the labels. This removes both possibilities.

1. **Write.** A model of another family writes new four-option questions in the
   same twenty subjects, today.
2. **Clean.** Two solvers of two further families answer each question blind.
   A question is kept only if both choose its key, so the kept questions are
   unambiguous by that consensus.
3. **Plant.** From the kept questions, a fixed sample is drawn, and in a fixed
   random fifth of it the key is moved to a random wrong option. Only this
   script knows which.
4. **Diagnose.** deepseek-v4.1-flash judges every item with the prompt, model
   settings and token budget of the first study, unchanged.

Planted errors on clean questions are easier to see than natural ones. The two
studies bracket the truth: natural errors where memorisation was possible, and
artificial errors where it was not.

Pre-registered in `experiments/DIAGNOSIS-UNSEEN-2026-10/PREREGISTRATION.md`.

  python scripts/diagnose_unseen.py --config ~/.ra-psi/run-config.json --key openrouter
  python scripts/diagnose_unseen.py --score-only
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import diagnose_flagged as first  # noqa: E402  (the first study's prompt and parser)
from validate_against_redux import wilson  # noqa: E402

EXPERIMENT = ROOT / "experiments" / "DIAGNOSIS-UNSEEN-2026-10"
SEED = 20261003
SUBJECTS = ["anatomy", "astronomy", "college biology", "college chemistry", "college physics",
            "computer security", "econometrics", "electrical engineering", "high school statistics",
            "international law", "jurisprudence", "machine learning", "medical genetics", "microeconomics",
            "nutrition", "philosophy", "professional accounting", "professional medicine", "virology",
            "world history"]
BATCHES_PER_SUBJECT, PER_BATCH = 5, 5
SAMPLE, PLANTED = 300, 60
BUDGET_USD = 7.0
WRITER = "google/gemini-3.6-flash"
SOLVERS = ("minimax/minimax-m3", "qwen/qwen3.5-122b-a10b")
DIAGNOSER = "deepseek/deepseek-v4.1-flash"
LETTERS = "ABCD"

WRITE_PROMPT = """Write {k} new multiple-choice exam questions in {subject}, at the level of a university course or a professional exam. Batch {batch}: choose sub-topics different from other batches by focusing on the sub-topics whose names start with the letters {letters}.

Each question must have exactly four options and exactly one correct option. Do not use "all of the above", "none of the above" or questions that depend on a figure. Vary the position of the correct option.

Reply with JSON only:
{{"questions": [{{"question": "...", "options": ["...", "...", "...", "..."], "answer": "A" | "B" | "C" | "D"}}]}}"""

SOLVE_PROMPT = """Answer this multiple-choice question in {subject}.

Question: {question}
{options}

Reply with JSON only: {{"answer": "A" | "B" | "C" | "D"}}"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def entry_for(model: str, location: dict, max_tokens: int, reasoning: bool) -> dict:
    entry = {"evaluator_id": model, "model": model, "endpoint": "https://openrouter.ai/api/v1/chat/completions",
             "json_mode": False, "max_tokens": max_tokens,
             **{k: v for k, v in location.items() if k in ("api_key_file", "api_key_env")}}
    if reasoning:
        entry["extra_body"] = {"reasoning": {"effort": "low"}}
    return entry


def ask_json(entry: dict, prompt: str) -> dict | None:
    from evaluate_experiment import AdapterError, call

    for _ in range(2):
        try:
            content, _ = call(entry, prompt, int(entry["max_tokens"]))
        except AdapterError:
            continue
        match = re.search(r"\{.*\}", content or "", re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


def cached(path: Path, make):
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    value = make()
    if value is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    return value


def write_stage(writer: dict | None, workers: int) -> list[dict]:
    folder = EXPERIMENT / "written"
    letters = ["A-E", "F-J", "K-O", "P-T", "U-Z"]
    jobs = [(s, b) for s in SUBJECTS for b in range(BATCHES_PER_SUBJECT)]

    def one(job):
        subject, batch = job
        path = folder / ("%s__%d.json" % (subject.replace(" ", "_"), batch))
        if writer is None and not path.is_file():
            return None
        return cached(path, lambda: ask_json(writer, WRITE_PROMPT.format(
            k=PER_BATCH, subject=subject, batch=batch + 1, letters=letters[batch])))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, jobs))
    items, seen = [], set()
    for (subject, batch), result in zip(jobs, results):
        for k, q in enumerate((result or {}).get("questions", [])):
            options, answer = q.get("options"), str(q.get("answer", "")).strip().upper()[:1]
            text = str(q.get("question", "")).strip()
            key = re.sub(r"\W+", " ", text.lower()).strip()
            if not text or not isinstance(options, list) or len(options) != 4 or answer not in LETTERS or key in seen:
                continue
            if len({re.sub(r"\W+", " ", str(o).lower()).strip() for o in options}) != 4:
                continue
            seen.add(key)
            items.append({"id": "%s-%d-%d" % (subject.replace(" ", "_"), batch, k), "subject": subject,
                          "question": text, "choices": [str(o) for o in options], "key": answer})
    return items


def solve_stage(items: list[dict], solvers: list[dict] | None, workers: int) -> dict[str, dict[str, str | None]]:
    folder = EXPERIMENT / "solved"
    answers: dict[str, dict[str, str | None]] = {}

    def one(pair):
        item, solver_model, solver = pair
        path = folder / ("%s__%s.json" % (item["id"], solver_model.replace("/", "_")))
        if solver is None and not path.is_file():
            return item["id"], solver_model, None
        options = "\n".join("%s. %s" % (l, t) for l, t in zip(LETTERS, item["choices"]))
        got = cached(path, lambda: ask_json(solver, SOLVE_PROMPT.format(
            subject=item["subject"], question=item["question"], options=options)) or {"answer": None})
        letter = str((got or {}).get("answer") or "").strip().upper()[:1]
        return item["id"], solver_model, letter if letter in LETTERS else None

    pairs = [(item, model, (solvers or {}).get(model) if solvers else None) for item in items for model in SOLVERS]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for item_id, model, letter in pool.map(one, pairs):
            answers.setdefault(item_id, {})[model] = letter
    return answers


def plant(clean: list[dict]) -> list[dict]:
    rng = random.Random(SEED)
    chosen = rng.sample(sorted(clean, key=lambda i: i["id"]), SAMPLE)
    planted_ids = set(i["id"] for i in rng.sample(chosen, PLANTED))
    out = []
    for item in chosen:
        record = dict(item, original_key=item["key"], planted=item["id"] in planted_ids)
        if record["planted"]:
            record["key"] = rng.choice([l for l in LETTERS if l != item["key"]])
        out.append(record)
    return out


def diagnose_stage(sample: list[dict], diagnoser: dict | None, workers: int) -> dict[str, dict]:
    folder = EXPERIMENT / "diagnosed"
    folder.mkdir(parents=True, exist_ok=True)
    out = {}

    def one(item):
        path = folder / (item["id"] + ".json")
        if path.is_file():
            return item["id"], json.loads(path.read_text(encoding="utf-8"))
        if diagnoser is None:
            return item["id"], {}
        from evaluate_experiment import AdapterError, call

        record = {"attempts": []}
        for _ in range(2):  # one retry, as in the first study
            try:
                content, served = call(diagnoser, first.render(item), int(diagnoser["max_tokens"]))
            except AdapterError as exc:
                record["attempts"].append({"error": str(exc)[:300]})
                continue
            parsed = first.parse(content)
            record["attempts"].append({"content": content[:4000], "served_model": served})
            if parsed:
                record.update(parsed)
                break
        record["asked_at_utc"] = now()
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        return item["id"], record

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for item_id, record in pool.map(one, sample):
            out[item_id] = record
    return out


def score(sample: list[dict], verdicts: dict[str, dict]) -> dict:
    rows = []
    for item in sample:
        got = verdicts.get(item["id"], {})
        rows.append({"id": item["id"], "subject": item["subject"], "planted": item["planted"],
                     "key": item["key"], "original_key": item["original_key"],
                     "verdict": got.get("verdict") or "NO_VERDICT", "best_option": got.get("best_option")})
    planted = [r for r in rows if r["planted"]]
    clean = [r for r in rows if not r["planted"]]
    called = [r for r in rows if r["verdict"] == "KEY_WRONG"]
    hits = sum(r["planted"] for r in called)
    caught = [r for r in planted if r["verdict"] == "KEY_WRONG"]
    right_fix = sum(r["best_option"] == r["original_key"] for r in caught)
    false_alarms = sum(r["verdict"] == "KEY_WRONG" for r in clean)
    base = PLANTED / SAMPLE

    def rate(k: int, n: int) -> dict:
        return {"hits": k, "n": n, "rate": round(k / n, 3) if n else None, "interval_95": wilson(k, n)}

    u1, u2, u3, u4 = rate(hits, len(called)), rate(len(caught), len(planted)), rate(false_alarms, len(clean)), \
        rate(right_fix, len(caught))
    sens, fpr = (u2["rate"] or 0.0), (u3["rate"] or 0.0)
    prev = 0.111  # key-error rate among flagged items in VALIDATION-REDUX-2026-10

    def held(ok):
        return "not computable" if ok is None else ("held" if ok else "FAILED")

    return {
        "sample": len(rows), "planted": len(planted), "base_rate": base,
        "U1_precision_of_KEY_WRONG": u1,
        "U2_planted_errors_called_KEY_WRONG": u2,
        "U3_KEY_WRONG_on_clean_items": u3,
        "U4_correct_option_named_when_caught": u4,
        "no_verdict": sum(r["verdict"] == "NO_VERDICT" for r in rows),
        "any_non_ok_on_clean_items": sum(r["verdict"] not in ("KEY_OK", "NO_VERDICT") for r in clean),
        "exploratory_precision_at_flagged_prevalence_0_111": round(sens * prev / (sens * prev + fpr * (1 - prev)), 3)
        if (sens or fpr) else None,
        "predictions": {
            "U1_precision_ge_0_40_and_lower_bound_above_0_20": held(
                None if not u1["n"] else u1["rate"] >= 2 * base and u1["interval_95"][0] > base),
            "U2_recall_ge_0_50": held(None if not u2["n"] else u2["hits"] / u2["n"] >= 0.5),
            "U3_false_key_wrong_on_clean_le_0_10": held(None if not u3["n"] else u3["hits"] / u3["n"] <= 0.10),
            "U4_names_original_key_ge_0_80_when_caught": held(None if not u4["n"] else u4["hits"] / u4["n"] >= 0.80),
        },
        "items": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--key", default="openrouter")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--score-only", action="store_true")
    args = parser.parse_args()

    writer = solvers = diagnoser = None
    if not args.score_only:
        import cost_guard

        table = cost_guard.prices()
        for model in (WRITER, DIAGNOSER) + SOLVERS:
            if model not in table:
                raise SystemExit("no published price for %s; refusing to run" % model)
        est = (len(SUBJECTS) * BATCHES_PER_SUBJECT * (400 / 3.5 * table[WRITER]["prompt"] + 6000 * table[WRITER]["completion"])
               + sum(len(SUBJECTS) * BATCHES_PER_SUBJECT * PER_BATCH * (800 / 3.5 * table[m]["prompt"] + 2000 * table[m]["completion"])
                     for m in SOLVERS)
               + SAMPLE * (1500 / 3.5 * table[DIAGNOSER]["prompt"] + 1500 * table[DIAGNOSER]["completion"]))
        print(json.dumps({"pessimistic_usd": round(est, 2), "budget_usd": BUDGET_USD}), flush=True)
        if est > BUDGET_USD:
            raise SystemExit("estimate exceeds the pre-registered budget; refusing to run")
        location = json.loads(args.config.expanduser().read_text(encoding="utf-8")).get("keys", {}).get(args.key)
        if not location:
            raise SystemExit("no key location configured for %r" % args.key)
        writer = entry_for(WRITER, location, 6000, reasoning=False)
        solvers = {m: entry_for(m, location, 2000, reasoning=True) for m in SOLVERS}
        diagnoser = entry_for(DIAGNOSER, location, 1500, reasoning=True)  # the first study's settings

    items = write_stage(writer, args.workers)
    answers = solve_stage(items, solvers, args.workers)
    clean = [i for i in items if all(answers.get(i["id"], {}).get(m) == i["key"] for m in SOLVERS)]
    print(json.dumps({"written": len(items), "kept_by_both_solvers": len(clean)}), flush=True)
    if len(clean) < SAMPLE:
        raise SystemExit("only %d clean questions; the pre-registered sample is %d. Stopping before any diagnosis."
                         % (len(clean), SAMPLE))
    sample = plant(clean)
    (EXPERIMENT / "sample.json").write_text(json.dumps(sample, ensure_ascii=False, indent=1), encoding="utf-8")
    verdicts = diagnose_stage(sample, diagnoser, args.workers)
    result = {"record_version": "RA-PSI-DIAGNOSIS-UNSEEN-V1",
              "preregistration": "experiments/DIAGNOSIS-UNSEEN-2026-10/PREREGISTRATION.md",
              "writer": WRITER, "solvers": list(SOLVERS), "diagnoser": DIAGNOSER, "scored_at_utc": now(),
              "written": len(items), "clean": len(clean), **score(sample, verdicts)}
    (EXPERIMENT / "result.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "items"}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
