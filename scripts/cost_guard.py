#!/usr/bin/env python3
"""Refuse to start a run that could cost more than the owner allowed.

The project now has paid credit on one provider. Credit removes the waiting, and
adds a way to fail that free quotas never had: spending. This guard makes cost a
checked number rather than a hope.

Before a run it fetches the provider's published prices, estimates the cost from
the number of calls and the sizes actually in the experiment, and compares it
with the `budget.max_usd` written in the experiment's policy. Over budget, the
run does not start. It also reads the account's spend so a run can be refused
when little credit is left.

Estimates are deliberately pessimistic: every prompt is counted at its full
length and every answer at its full token budget.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "RA-PSI-cost-guard/1.0 (+https://github.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026)"


def fetch_json(url: str, key: str | None = None, attempts: int = 3) -> dict:
    """Read JSON, retrying transport failures: a dropped connection while
    pricing a run must not kill the run itself."""
    import time

    headers = {"User-Agent": USER_AGENT}
    if key:
        headers["Authorization"] = "Bearer " + key
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
                return json.load(response)
        except (OSError, ValueError) as exc:
            last = exc
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("cannot read %s: %s" % (url, last))


def prices(base: str = "https://openrouter.ai/api/v1") -> dict[str, dict]:
    """Published price per token, by model id. Free models price at zero."""
    data = fetch_json(base + "/models").get("data", [])
    table = {}
    for model in data:
        pricing = model.get("pricing") or {}
        try:
            table[model["id"]] = {"prompt": float(pricing.get("prompt", 0)), "completion": float(pricing.get("completion", 0))}
        except (TypeError, ValueError):
            continue
    return table


def estimate(calls: int, prompt_chars: int, max_output_tokens: int, price: dict) -> float:
    """Pessimistic cost in USD: full prompt, full output budget, every call."""
    prompt_tokens = prompt_chars / 3.5
    return calls * (prompt_tokens * price["prompt"] + max_output_tokens * price["completion"])


def account(key: str, base: str = "https://openrouter.ai/api/v1") -> dict:
    data = fetch_json(base + "/key", key).get("data", {})
    return {"paid": not data.get("is_free_tier", True), "usage_usd": data.get("usage"),
            "limit_usd": data.get("limit"), "remaining_usd": data.get("limit_remaining"),
            "free_requests_left": (data.get("free_model_daily_requests") or {}).get("remaining")}


def plan_for_anchored_chain(experiment: Path, policy: dict) -> list[dict]:
    """What a chain experiment will send: every hop, every arm, every document.

    A guard that does not know a design cannot refuse a run under it, so a new
    design is priced here before it is run rather than after.
    """
    regimes = policy["regimes"]
    repeats, hops = int(policy["repeats"]), max(policy["read_at"])
    documents = len(policy["documents"])
    writer_calls = documents * repeats * hops * len(regimes)
    # The anchored arm spends one extra call per hop asking what to retrieve;
    # hop 1 reads the document itself and asks for nothing.
    asking = documents * repeats * (hops - 1) if "anchored" in regimes else 0
    generation = policy["generator"]
    document_chars = max(len((experiment / name).read_text(encoding="utf-8")) for name in policy["documents"])
    index_chars = max(len(json.dumps(json.loads((experiment / path).read_text(encoding="utf-8"))))
                      for path in policy["ledgers"].values())
    prompt_chars = document_chars + index_chars + 1500
    steps = [{"stage": "writing", "model": generation["model"], "calls": writer_calls + asking,
              "endpoint": generation.get("endpoint", ""), "prompt_chars": prompt_chars,
              "max_output_tokens": int(generation.get("max_tokens", 5000))}]
    reader = policy["reader"]
    quiz_chars = max(len((experiment / path).read_text(encoding="utf-8")) for path in policy["quizzes"].values())
    steps.append({"stage": "reading", "model": reader["model"],
                  "calls": documents * repeats * len(regimes) * len(policy["read_at"]),
                  "endpoint": reader.get("endpoint", ""), "prompt_chars": quiz_chars + 3000,
                  "max_output_tokens": int(reader.get("max_tokens", 2000))})
    return steps


def plan_for(experiment_id: str) -> list[dict]:
    """What a quiz experiment will send, from its own policy and files."""
    experiment = ROOT / "experiments" / experiment_id
    policy = json.loads((experiment / "evaluation_policy.json").read_text(encoding="utf-8"))
    if policy.get("design") == "anchored_chain":
        return plan_for_anchored_chain(experiment, policy)
    generation = policy["generation"]
    pairs = len(generation["seeds"])
    state_chars = max(len((experiment / generation[name]).read_text(encoding="utf-8"))
                      for name in ("baseline_state", "structured_state"))
    prompt_chars = state_chars + len((experiment / "TEST_PROMPT.md").read_text(encoding="utf-8"))
    steps = [{"stage": "generation", "model": generation["model"], "calls": pairs * 2,
              "endpoint": generation.get("endpoint", ""),
              "prompt_chars": prompt_chars, "max_output_tokens": int(generation.get("max_output_tokens", 1000))}]
    # A reader already declared unable is not the one that will be billed.
    skip = set(policy.get("skip_readers") or ())
    readers = [rung for rung in (policy.get("reader_ladder") or [policy["reader"]])
               if rung.get("evaluator_id") not in skip]
    if not readers:
        raise SystemExit("every reader in the ladder has been skipped")
    quiz = json.loads((experiment / policy["quiz"]["file"]).read_text(encoding="utf-8"))
    quiz_chars = len(json.dumps(quiz)) + 2000  # questions, options and header
    steps.append({"stage": "reading", "model": readers[0]["model"], "calls": pairs * 2,
                  "endpoint": readers[0].get("endpoint", ""),
                  "prompt_chars": quiz_chars + 3000, "max_output_tokens": int(readers[0].get("max_tokens", 2000))})
    return steps


def check(experiment_id: str, key_file: str | None) -> dict:
    policy = json.loads((ROOT / "experiments" / experiment_id / "evaluation_policy.json").read_text(encoding="utf-8"))
    budget = policy.get("budget") or {}
    allowed = float(budget.get("max_usd", 0.0))
    table = prices()
    steps, total = [], 0.0
    for step in plan_for(experiment_id):
        # Only calls billed through the credited provider can spend the credit.
        # Another provider's free tier costs nothing here and is reported as such.
        billed = "openrouter.ai" in step.get("endpoint", "")
        price = table.get(step["model"], {"prompt": 0.0, "completion": 0.0}) if billed else {"prompt": 0.0, "completion": 0.0}
        cost = estimate(step["calls"], step["prompt_chars"], step["max_output_tokens"], price)
        total += cost
        steps.append({**step, "estimated_usd": round(cost, 4), "billed_here": billed,
                      "priced": (step["model"] in table) if billed else True,
                      "free": price["prompt"] == 0 and price["completion"] == 0})
    report = {"experiment_id": experiment_id, "estimated_usd": round(total, 4), "allowed_usd": allowed, "steps": steps}
    if key_file:
        report["account"] = account(Path(key_file).expanduser().read_text(encoding="utf-8-sig").strip())
    unpriced = [step["model"] for step in steps if not step["priced"]]
    if unpriced:
        report.update(status="REFUSED", reason="no published price for %s" % ", ".join(sorted(set(unpriced))))
    elif total > allowed:
        report.update(status="REFUSED", reason="estimate %.4f USD exceeds the budget of %.4f USD" % (total, allowed))
    else:
        report.update(status="WITHIN_BUDGET")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--key-file", default="~/.ra-psi/keys/openrouter.key")
    args = parser.parse_args()
    report = check(args.experiment, args.key_file)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["status"] == "WITHIN_BUDGET" else 1)


if __name__ == "__main__":
    main()
