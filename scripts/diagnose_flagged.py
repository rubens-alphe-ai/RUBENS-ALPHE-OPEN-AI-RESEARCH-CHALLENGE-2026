#!/usr/bin/env python3
"""Can a cheap model say *what* is wrong with a flagged item, not just *which* to read?

Pre-registered in `experiments/DIAGNOSIS-REDUX-2026-10/PREREGISTRATION.md`
before any model was asked. The item flags already find where the expert-found
key errors are (VALIDATION-REDUX-2026-10): reading the 7% of items on the
screening list finds 54% of them. But 78% of those flagged items are fine, so a
buyer still has to read every one. This asks one inexpensive model, blind to the
flag, to judge each item and its key, and scores its verdicts against the
MMLU-Redux 2.0 expert labels (CC BY 4.0).

The model sees the question, the four options and the key. It is never told
whether the item was flagged, nor what the experts said.

  python scripts/diagnose_flagged.py --config ~/.ra-psi/run-config.json --key openrouter
  python scripts/diagnose_flagged.py --score-only
"""

from __future__ import annotations

import argparse
import ast
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

import validate_against_redux as var  # noqa: E402

EXPERIMENT = ROOT / "experiments" / "DIAGNOSIS-REDUX-2026-10"
VALIDATION = ROOT / "experiments" / "VALIDATION-REDUX-2026-10" / "result.json"
SEED = 20261003
CONTROLS = 200
LETTERS = "ABCD"
VERDICTS = ("KEY_OK", "KEY_WRONG", "MULTIPLE_CORRECT", "NO_CORRECT_ANSWER", "UNCLEAR")
BUDGET_USD = 3.0

PROMPT = """You are reviewing one multiple-choice exam question for defects. The answer key is given. Judge it as a careful expert in the subject ({subject}).

Question: {question}
{options}
Answer key: {key}

Reply with JSON only, in this form:
{{"verdict": "KEY_OK" | "KEY_WRONG" | "MULTIPLE_CORRECT" | "NO_CORRECT_ANSWER" | "UNCLEAR", "best_option": "A" | "B" | "C" | "D" | null, "reason": "<one sentence>"}}

- KEY_OK: the keyed option is the single best answer.
- KEY_WRONG: another option is clearly the correct one; name it in best_option.
- MULTIPLE_CORRECT: more than one option is defensibly correct.
- NO_CORRECT_ANSWER: none of the options is correct.
- UNCLEAR: the question or the options are too ambiguous to answer."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def choices_of(row: dict) -> list[str]:
    raw = row["choices"]
    return list(raw) if isinstance(raw, list) else list(ast.literal_eval(raw))


def load_items() -> list[dict]:
    """The validated items, with the Redux row each one was matched to."""
    validated = {(i["subject"], i["item"]): i for i in json.loads(VALIDATION.read_text(encoding="utf-8"))["items"]}
    out = []
    for subject, slug in var.subjects():
        manifest_path = var.SURVEY / "tables" / ("%s.provenance.json" % slug)
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        instances = var.get_json(manifest["runs"][0]["instances_url"], "helm-%s.json" % subject)
        by_text: dict[str, list[str]] = {}
        for inst in instances:
            by_text.setdefault(var.normalise(inst["input"]["text"]), []).append(inst["id"])
        redux = var.get_json(var.REDUX % var.urllib.parse.quote(subject), "redux-%s.json" % subject)
        for row in (r["row"] for r in redux.get("rows", [])):
            ids = by_text.get(var.normalise(row["question"]), [])
            if len(ids) != 1 or (subject, ids[0]) not in validated:
                continue
            choices = choices_of(row)
            if len(choices) != 4:
                continue
            out.append({**validated[(subject, ids[0])], "question": row["question"], "choices": choices,
                        "key": LETTERS[int(row["answer"])]})
    return out


def sample(items: list[dict]) -> list[dict]:
    """Every screening-flagged item, and a fixed random sample of unflagged ones."""
    flagged = [i for i in items if i["screening"]]
    unflagged = sorted((i for i in items if not i["screening"]), key=lambda i: (i["subject"], i["item"]))
    controls = random.Random(SEED).sample(unflagged, CONTROLS)
    return flagged + controls


def render(item: dict) -> str:
    options = "\n".join("%s. %s" % (letter, text) for letter, text in zip(LETTERS, item["choices"]))
    return PROMPT.format(subject=item["subject"].replace("_", " "), question=item["question"].strip(),
                         options=options, key=item["key"])


def parse(content: str) -> dict | None:
    match = re.search(r"\{.*\}", content or "", re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    verdict = str(data.get("verdict", "")).strip().upper()
    if verdict not in VERDICTS:
        return None
    best = data.get("best_option")
    best = str(best).strip().upper()[:1] if best else None
    return {"verdict": verdict, "best_option": best if best and best in LETTERS else None,
            "reason": str(data.get("reason", ""))[:400]}


def ask(entry: dict, item: dict, raw_dir: Path) -> dict:
    from evaluate_experiment import AdapterError, call

    name = "%s__%s" % (item["subject"], item["item"])
    raw = raw_dir / (name + ".json")
    if raw.is_file():
        return json.loads(raw.read_text(encoding="utf-8"))
    record = {"subject": item["subject"], "item": item["item"], "attempts": []}
    for _ in range(2):  # one retry on an unusable answer, as pre-registered
        try:
            content, served = call(entry, render(item), int(entry["max_tokens"]))
        except AdapterError as exc:
            record["attempts"].append({"error": str(exc)[:300]})
            continue
        parsed = parse(content)
        record["attempts"].append({"content": content[:4000], "served_model": served})
        if parsed:
            record.update(parsed)
            break
    record["asked_at_utc"] = now()
    raw.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


def estimate_usd(prompts: list[str], max_tokens: int, price: dict) -> float:
    return sum(len(p) / 3.5 * price["prompt"] + max_tokens * price["completion"] for p in prompts)


def rate(hits: int, n: int) -> dict:
    return {"n": n, "hits": hits, "rate": round(hits / n, 3) if n else None, "interval_95": var.wilson(hits, n)}


def score(chosen: list[dict], answers: dict) -> dict:
    rows = []
    for item in chosen:
        got = answers.get((item["subject"], item["item"]), {})
        verdict = got.get("verdict")
        rows.append({"subject": item["subject"], "item": item["item"], "screening": item["screening"],
                     "strict": item["strict"], "error_type": item["error_type"], "key_error": item["key_error"],
                     "any_error": item["any_error"], "verdict": verdict or "NO_VERDICT",
                     "best_option": got.get("best_option")})
    flagged = [r for r in rows if r["screening"]]
    controls = [r for r in rows if not r["screening"]]
    key_errors = [r for r in flagged if r["key_error"]]
    said_wrong = [r for r in flagged if r["verdict"] == "KEY_WRONG"]
    said_problem = [r for r in flagged if r["verdict"] not in ("KEY_OK", "NO_VERDICT")]

    flag_key_rate = sum(r["key_error"] for r in flagged) / len(flagged)
    flag_any_rate = sum(r["any_error"] for r in flagged) / len(flagged)
    d1 = rate(sum(r["key_error"] for r in said_wrong), len(said_wrong))
    d2 = rate(sum(r["verdict"] == "KEY_WRONG" for r in key_errors), len(key_errors))
    d3 = rate(sum(r["any_error"] for r in said_problem), len(said_problem))
    d4 = rate(sum(r["verdict"] == "KEY_WRONG" for r in controls), len(controls))

    def held(ok: bool | None) -> str:
        return "not computable" if ok is None else ("held" if ok else "FAILED")

    predictions = {
        "D1_key_wrong_precision_ge_2x_flag_rate_and_lower_bound_above_it": held(
            None if not d1["n"] else (d1["rate"] >= 2 * flag_key_rate and d1["interval_95"][0] > flag_key_rate)),
        "D2_keeps_half_the_key_errors": held(None if not d2["n"] else d2["hits"] / d2["n"] >= 0.5),
        "D3_problem_precision_ge_1_5x_and_lower_bound_above": held(
            None if not d3["n"] else (d3["rate"] >= 1.5 * flag_any_rate and d3["interval_95"][0] > flag_any_rate)),
        "D4_key_wrong_on_unflagged_le_10pct": held(None if not d4["n"] else d4["hits"] / d4["n"] <= 0.10),
    }
    by_verdict = {}
    for verdict in VERDICTS + ("NO_VERDICT",):
        group = [r for r in flagged if r["verdict"] == verdict]
        by_verdict[verdict] = {"flagged_items": len(group), "expert_key_error": sum(r["key_error"] for r in group),
                               "expert_any_error": sum(r["any_error"] for r in group)}
    return {
        "flagged_items": len(flagged), "control_items": len(controls),
        "flag_only": {"key_error_rate": round(flag_key_rate, 3), "any_error_rate": round(flag_any_rate, 3)},
        "D1_expert_key_error_among_KEY_WRONG": d1,
        "D2_share_of_expert_key_errors_called_KEY_WRONG": d2,
        "D3_expert_any_error_among_any_problem_verdict": d3,
        "D4_KEY_WRONG_rate_on_unflagged_controls": d4,
        "no_verdict": sum(r["verdict"] == "NO_VERDICT" for r in rows),
        "predictions": predictions,
        "flagged_by_verdict": by_verdict,
        "items": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--key", default="openrouter")
    parser.add_argument("--model", default="deepseek/deepseek-v4.1-flash")
    parser.add_argument("--endpoint", default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--max-tokens", type=int, default=1500)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--score-only", action="store_true")
    args = parser.parse_args()

    chosen = sample(load_items())
    raw_dir = EXPERIMENT / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if not args.score_only:
        import cost_guard

        price = cost_guard.prices().get(args.model)
        if price is None:
            raise SystemExit("no published price for %s; refusing to run" % args.model)
        cost = estimate_usd([render(i) for i in chosen], args.max_tokens, price)
        print(json.dumps({"items": len(chosen), "pessimistic_usd": round(cost, 3), "budget_usd": BUDGET_USD}))
        if cost > BUDGET_USD:
            raise SystemExit("estimate exceeds the pre-registered budget; refusing to run")
        private = json.loads(args.config.expanduser().read_text(encoding="utf-8"))
        location = private.get("keys", {}).get(args.key)
        if not location:
            raise SystemExit("no key location configured for %r" % args.key)
        entry = {"evaluator_id": "diagnose", "model": args.model, "endpoint": args.endpoint, "json_mode": False,
                 "max_tokens": args.max_tokens, "extra_body": {"reasoning": {"effort": "low"}},
                 **{k: v for k, v in location.items() if k in ("api_key_file", "api_key_env")}}
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            list(pool.map(lambda item: ask(entry, item, raw_dir), chosen))

    answers = {}
    for path in raw_dir.glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        answers[(record["subject"], record["item"])] = record
    result = {"record_version": "RA-PSI-DIAGNOSIS-REDUX-V1",
              "preregistration": "experiments/DIAGNOSIS-REDUX-2026-10/PREREGISTRATION.md",
              "model": args.model, "scored_at_utc": now(), **score(chosen, answers)}
    (EXPERIMENT / "result.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("items",)}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
