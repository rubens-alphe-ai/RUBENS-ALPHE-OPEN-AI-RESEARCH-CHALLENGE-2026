#!/usr/bin/env python3
"""Find benchmark comparisons in new model cards, and say which gaps are established.

Model cards on the Hugging Face Hub often carry a table: our model against the
strongest other models, benchmark by benchmark. This reads the cards of
recently trending text-generation models published by organisations, asks one
inexpensive model to extract each comparison, keeps only those whose two scores
appear verbatim in the card, and tests the gap against the size of the
benchmark.

The test is unpaired — two proportions, each over the benchmark's questions —
because a card gives scores, not per-item results. It is the conservative
reading: a paired test on per-item results separates more pairs. Benchmark
sizes are those of the public test sets, checked against the Hugging Face
datasets server on 2026-10-03; where a name is ambiguous, the comparison is
skipped rather than guessed.

The output is for private, one-to-one notes to the authors, never for public
naming: "not established" means not shown at this test size, not false.

  python scripts/claim_scanner.py --config ~/.ra-psi/run-config.json --key openrouter --out .private/claims-scan
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

Z95, Z80 = 1.959964, 0.841621
HUB = "https://huggingface.co"
AGENT = "RA-PSI-claim-scanner/1.0 (+https://github.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026)"
BUDGET_USD = 2.0

# Public test-set sizes, each checked on datasets-server.huggingface.co/size
# (dataset, config, split) on 2026-10-03. Order matters: the first match wins,
# so the more specific names come first.
BENCHMARKS = [
    ("MMLU-Pro", re.compile(r"^mmlu[\s_-]*pro\b", re.I), 12032, "TIGER-Lab/MMLU-Pro default/test"),
    ("MMLU-Redux", re.compile(r"^mmlu[\s_-]*redux", re.I), None, "ambiguous version; skipped"),
    ("MMLU", re.compile(r"^mmlu\b(?![\s_-]*(pro|redux|prox))", re.I), 14042, "cais/mmlu all/test"),
    ("GPQA Diamond", re.compile(r"^gpqa[\s_-]*(diamond|◆|-d\b)", re.I), 198, "fingertap/GPQA-Diamond default/test"),
    ("GSM8K", re.compile(r"^gsm[\s_-]*8k\b", re.I), 1319, "openai/gsm8k main/test"),
    ("MATH-500", re.compile(r"^math[\s_-]*500\b", re.I), 500, "HuggingFaceH4/MATH-500 default/test"),
    ("HumanEval", re.compile(r"^humaneval\b(?![\s_+-]*(\+|plus|x|-?mul))", re.I), 164, "openai/openai_humaneval test"),
    ("IFEval", re.compile(r"^ifeval\b", re.I), 541, "google/IFEval default/train"),
    ("SWE-bench Verified", re.compile(r"^swe[\s_-]*bench[\s_-]*verified\b", re.I), 500, "princeton-nlp/SWE-bench_Verified test"),
    ("AIME 2024", re.compile(r"^aime[\s_'-]*(20)?24\b", re.I), 30, "HuggingFaceH4/aime_2024 train"),
    ("AIME 2026", re.compile(r"^aime[\s_'-]*(20)?26\b", re.I), 30, "MathArena/aime_2026 train"),
    ("HMMT Feb 2026", re.compile(r"^hmmt[\s_-]*(feb(ruary)?)?[\s_'-]*(20)?26\b", re.I), 33, "MathArena/hmmt_feb_2026 train"),
    ("IFBench", re.compile(r"^ifbench\b", re.I), 300, "allenai/IFBench_test train"),
    ("SWE-bench Pro", re.compile(r"^swe[\s_-]*bench[\s_-]*pro\b", re.I), 731, "ScaleAI/SWE-bench_Pro v1/test (default has 642; the larger size is the conservative choice)"),
    ("AIME 2025", re.compile(r"^aime[\s_'-]*(20)?25\b", re.I), 30, "math-ai/aime25 test"),
    ("ARC-Challenge", re.compile(r"^arc[\s_-]*(c\b|chal)", re.I), 1172, "allenai/ai2_arc ARC-Challenge/test"),
    ("ARC-Easy", re.compile(r"^arc[\s_-]*(e\b|easy)", re.I), 2376, "allenai/ai2_arc ARC-Easy/test"),
    ("HellaSwag", re.compile(r"^hellaswag\b", re.I), 10042, "Rowan/hellaswag validation"),
    ("TruthfulQA", re.compile(r"^truthful[\s_-]*qa\b", re.I), 817, "truthfulqa/truthful_qa validation"),
    ("Winogrande", re.compile(r"^winogrande\b", re.I), 1267, "allenai/winogrande validation"),
    ("MBPP", re.compile(r"^mbpp\b(?![\s_+-]*(\+|plus))", re.I), 500, "google-research-datasets/mbpp full/test (sanitized has 257; the larger size is the conservative choice)"),
]
SKIP_NAME = re.compile(r"gguf|awq|gptq|exl\d|bpw|abliterat|uncensor|heretic|lora|mlx|fp8|int4|int8|bnb|4bit|8bit|quant|distill-test|nvfp4|fp4\b|dflash|obliterat|prefiller", re.I)

PROMPT = """Below is the model card of the AI model "{model}". Find every benchmark table or sentence in which this model's score is compared with other models' scores.

For each benchmark, return ONE comparison: this model against the strongest OTHER model listed for that benchmark in the same table (if this model is first, the runner-up; if it is behind, the leader). Copy the two scores exactly as written in the card, digits and decimals unchanged. Skip benchmarks where only this model's score is given, where scores are not percentages or accuracies, or where lower is better.

Reply with JSON only:
{{"comparisons": [{{"benchmark": "<name as written>", "this_model_score": "<as written>", "other_model": "<name as written>", "other_model_score": "<as written>"}}]}}

Model card:
<<<
{card}
>>>"""


def get(url: str, as_json: bool = True, timeout: int = 60):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", "replace")
            return json.loads(body) if as_json else body
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 404):
                return None
            time.sleep(3 * (attempt + 1))
        except Exception:  # noqa: BLE001
            time.sleep(3 * (attempt + 1))
    return None


def candidates(limit: int, days: int, min_likes: int) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    models = get("%s/api/models?pipeline_tag=text-generation&sort=trendingScore&direction=-1&limit=%d" % (HUB, limit)) or []
    out, orgs = [], {}
    for m in models:
        created = m.get("createdAt") or ""
        if not created or datetime.fromisoformat(created.replace("Z", "+00:00")) < since:
            continue
        if (m.get("likes") or 0) < min_likes or SKIP_NAME.search(m["id"]):
            continue
        author = m["id"].split("/", 1)[0]
        if author not in orgs:
            orgs[author] = get("%s/api/organizations/%s/overview" % (HUB, author)) is not None
        if orgs[author]:
            out.append({"model": m["id"], "organisation": author, "created": created[:10], "likes": m.get("likes")})
    return out


def benchmark_of(name: str, card: str) -> tuple[str, int, str] | None:
    clean = re.sub(r"[*`_]+", "", name).strip()
    for label, pattern, size, source in BENCHMARKS:
        if pattern.search(clean):
            return None if size is None else (label, size, source)
    return None


def cells_of(line: str) -> list[str]:
    return [re.sub(r"[*`_]+", "", cell).strip() for cell in line.split("|")]


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def table_rows(card: str) -> list[list[str]]:
    """Markdown rows, plus HTML table rows rewritten as pipe-separated cells."""
    text = re.sub(r"(?is)<tr\b.*?</tr>", lambda m: m.group(0).replace("\n", " "), card)
    text = re.sub(r"(?i)</t[dh]>", " | ", text)
    text = re.sub(r"(?i)</tr>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return [cells_of(line) for line in text.splitlines() if "|" in line]


def same_table_row(card: str, benchmark: str, this_model: str, other_model: str, mine: str, theirs: str) -> bool:
    """Guard against an extraction that pairs numbers from different rows or columns.

    Benchmarks as rows: one row holds the benchmark name and both scores.
    Benchmarks as columns: one row holds this model's name and its score, and
    another holds the other model's name and its score. Names are compared
    without spaces or punctuation, so "Laguna XS 2.1" matches "Laguna-XS-2.1".
    """
    bench = squash(benchmark)
    short = squash(this_model.split("/", 1)[-1])
    other = squash(other_model)
    rows = table_rows(card)
    for cells in rows:
        if bench and any(bench in squash(c) for c in cells) and mine in cells and theirs in cells:
            return True
    has_mine = any(short and any(short in squash(c) for c in cells) and mine in cells for cells in rows)
    has_theirs = any(other and any(other in squash(c) for c in cells) and theirs in cells for cells in rows)
    return has_mine and has_theirs


def as_proportion(text: str) -> float | None:
    match = re.fullmatch(r"\s*(\d{1,3}(?:[.,]\d+)?)\s*%?\s*", str(text))
    if not match:
        return None
    digits = match.group(1)
    value = float(digits.replace(",", "."))
    if value > 100:
        return None
    # "0.853" is a proportion; "85.3", "85" and "85.3%" are percentages.
    if "%" not in text and value <= 1 and re.search(r"[.,]", digits):
        return value
    return value / 100


def verdict(p_this: float, p_other: float, n: int) -> dict:
    gap = p_this - p_other
    var = p_this * (1 - p_this) + p_other * (1 - p_other)
    se = math.sqrt(var / n)
    lo, hi = gap - Z95 * se, gap + Z95 * se
    need = math.ceil((Z95 + Z80) ** 2 * var / gap ** 2) if gap else None
    established = gap != 0 and (lo > 0 or hi < 0)
    return {"gap_pts": round(100 * gap, 2), "interval_95_pts": [round(100 * lo, 2), round(100 * hi, 2)],
            "established": established, "questions_needed_80pct": need}


def scan(model: dict, entry: dict | None, cache: Path) -> dict:
    from evaluate_experiment import AdapterError, call

    safe = model["model"].replace("/", "__")
    card_path, reply_path = cache / (safe + ".md"), cache / (safe + ".extract.json")
    if card_path.is_file():
        card = card_path.read_text(encoding="utf-8")
    else:
        card = get("%s/%s/raw/main/README.md" % (HUB, model["model"]), as_json=False) or ""
        card_path.write_text(card, encoding="utf-8")
    record = {**model, "comparisons": [], "rejected": []}
    cells = (cell.strip(" *`_") for line in card.splitlines() for cell in line.split("|"))
    if not any(pattern.search(cell) for cell in cells for _, pattern, _, _ in BENCHMARKS):
        record["status"] = "no known benchmark in the card"
        return record
    if reply_path.is_file():
        extracted = json.loads(reply_path.read_text(encoding="utf-8"))
    elif entry is None:
        record["status"] = "not extracted (score-only run)"
        return record
    else:
        try:
            content, _ = call(entry, PROMPT.format(model=model["model"], card=card[:40000]), int(entry["max_tokens"]))
            match = re.search(r"\{.*\}", content or "", re.S)
            extracted = json.loads(match.group(0)) if match else {"comparisons": []}
        except (AdapterError, json.JSONDecodeError) as exc:
            record["status"] = "extraction failed: %s" % str(exc)[:120]
            return record
        reply_path.write_text(json.dumps(extracted, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in extracted.get("comparisons", []):
        mine, theirs = str(c.get("this_model_score", "")), str(c.get("other_model_score", ""))
        bench = benchmark_of(str(c.get("benchmark", "")), card)
        reason = None
        if bench is None:
            reason = "benchmark not in the verified list"
        elif mine not in card or theirs not in card:
            reason = "a score does not appear verbatim in the card"
        elif not same_table_row(card, str(c.get("benchmark", "")), model["model"], str(c.get("other_model", "")),
                                mine, theirs):
            reason = "the two scores could not be placed on the benchmark's row or on their models' rows"
        else:
            p_mine, p_theirs = as_proportion(mine), as_proportion(theirs)
            if p_mine is None or p_theirs is None:
                reason = "a score is not a percentage"
        if reason:
            record["rejected"].append({**c, "reason": reason})
            continue
        label, n, source = bench
        record["comparisons"].append({"benchmark": label, "questions": n, "size_source": source,
                                      "this_score": mine, "other_model": c.get("other_model"), "other_score": theirs,
                                      **verdict(p_mine, p_theirs, n)})
    record["status"] = "scanned"
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--key", default="openrouter")
    parser.add_argument("--model", default="deepseek/deepseek-v4.1-flash")
    parser.add_argument("--endpoint", default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument("--limit", type=int, default=400, help="trending models to look at")
    parser.add_argument("--days", type=int, default=60, help="only models created this recently")
    parser.add_argument("--min-likes", type=int, default=20)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cache = args.out / "cards"
    cache.mkdir(parents=True, exist_ok=True)
    models = candidates(args.limit, args.days, args.min_likes)
    entry = None
    if args.config:
        import cost_guard

        price = cost_guard.prices().get(args.model)
        if price is None:
            raise SystemExit("no published price for %s; refusing to run" % args.model)
        pessimistic = len(models) * (40000 / 3.5 * price["prompt"] + args.max_tokens * price["completion"])
        print(json.dumps({"models": len(models), "pessimistic_usd": round(pessimistic, 3), "budget_usd": BUDGET_USD}))
        if pessimistic > BUDGET_USD:
            raise SystemExit("estimate exceeds the budget; lower --limit")
        location = json.loads(args.config.expanduser().read_text(encoding="utf-8")).get("keys", {}).get(args.key)
        if not location:
            raise SystemExit("no key location configured for %r" % args.key)
        entry = {"evaluator_id": "claim-scanner", "model": args.model, "endpoint": args.endpoint, "json_mode": False,
                 "max_tokens": args.max_tokens, "extra_body": {"reasoning": {"effort": "low"}},
                 **{k: v for k, v in location.items() if k in ("api_key_file", "api_key_env")}}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        records = list(pool.map(lambda m: scan(m, entry, cache), models))
    found = [r for r in records if r["comparisons"]]
    summary = {
        "scanned_at_utc": datetime.now(timezone.utc).isoformat(),
        "models_considered": len(models),
        "models_with_testable_comparisons": len(found),
        "comparisons": sum(len(r["comparisons"]) for r in found),
        "established": sum(c["established"] for r in found for c in r["comparisons"]),
        "not_established": sum(not c["established"] for r in found for c in r["comparisons"]),
    }
    (args.out / "scan.json").write_text(json.dumps({"summary": summary, "models": records}, indent=1, ensure_ascii=False),
                                         encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
