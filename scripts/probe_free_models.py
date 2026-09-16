#!/usr/bin/env python3
"""Find which free models can actually do an evaluation job, in minutes.

During MEM-002 a second evaluator was found by trial and error over several
hours: a model listed as free answered HTTP 429 from a shared upstream pool,
another timed out, another accepted small requests but not a real batch.
A model list says what exists; only a request of the real size says what works.

This script lists an OpenAI-compatible provider's models, keeps the free ones,
and sends each one request of the size of a real batch. The filler text is
neutral and contains no experiment content, so probing reveals nothing and
spends nothing that matters. Results are ranked and cached outside the public
tree, so the next choice starts from measurements instead of guesses.

Selecting an evaluator from this ranking is still a decision that an experiment
records before scoring (see evaluation_policy.json, scorer_ladder).

Example:
  python scripts/probe_free_models.py --base https://openrouter.ai/api/v1 \
      --key-file ~/.ra-psi/keys/openrouter.txt --prompt-tokens 4000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_adapter import USER_AGENT, AdapterConfig, AdapterError, build_adapter  # noqa: E402

FILLER_SENTENCE = "The river passes the old mill, turns east below the bridge and reaches the lake by evening. "
DEFAULT_CACHE = Path("~/.ra-psi/model_probe.json")


def filler(prompt_tokens: int) -> str:
    # About 20 tokens per sentence; the closing instruction keeps the answer short.
    body = FILLER_SENTENCE * max(1, prompt_tokens // 20)
    return body + '\nReply with the JSON object {"ok": true} and nothing else.'


def is_free(model: dict) -> bool:
    if str(model.get("id", "")).endswith(":free"):
        return True
    pricing = model.get("pricing") or {}
    try:
        return bool(pricing) and float(pricing.get("prompt", 1)) == 0 and float(pricing.get("completion", 1)) == 0
    except (TypeError, ValueError):
        return False


def list_models(base: str, key: str) -> list[dict]:
    request = urllib.request.Request(base.rstrip("/") + "/models",
                                     headers={"Authorization": "Bearer " + key, "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8")).get("data", [])


def probe(base: str, key_file: str, model_id: str, prompt: str, max_tokens: int, timeout: int) -> dict:
    adapter = build_adapter(AdapterConfig(
        provider="openai-compatible", model=model_id, endpoint=base.rstrip("/") + "/chat/completions",
        temperature=0.0, max_output_tokens=max_tokens, timeout_seconds=timeout, think=None,
        api_key_file=key_file))
    started = time.monotonic()
    try:
        content = adapter.generate(prompt, seed=1)
        status, detail = "OK", content.strip()[:60]
    except AdapterError as exc:
        text = str(exc)
        status = ("RATE_LIMITED" if "429" in text else "TIMEOUT" if "timed out" in text
                  else "TRUNCATED" if "truncated" in text else "FAILED")
        detail = text[:160]
    return {"model": model_id, "status": status, "seconds": round(time.monotonic() - started, 1),
            "served_model": getattr(adapter, "last_served_model", None), "detail": detail}


def rank(results: list[dict]) -> list[dict]:
    order = {"OK": 0, "TRUNCATED": 1, "RATE_LIMITED": 2, "TIMEOUT": 3, "FAILED": 4}
    return sorted(results, key=lambda item: (order.get(item["status"], 9), item["seconds"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", required=True, help="API base URL, e.g. https://openrouter.ai/api/v1")
    parser.add_argument("--key-file", required=True, help="file holding the API key (never printed)")
    parser.add_argument("--prompt-tokens", type=int, default=4000, help="size of a real batch")
    parser.add_argument("--max-tokens", type=int, default=400)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--only", nargs="*", default=None, help="probe these model ids instead of all free ones")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args()

    key = Path(args.key_file).expanduser().read_text(encoding="utf-8").strip()
    models = args.only or sorted(model["id"] for model in list_models(args.base, key) if is_free(model))
    prompt = filler(args.prompt_tokens)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(lambda model_id: probe(args.base, args.key_file, model_id, prompt,
                                                       args.max_tokens, args.timeout), models))
    report = {"probed_at_utc": datetime.now(timezone.utc).isoformat(), "base": args.base,
              "prompt_tokens": args.prompt_tokens, "results": rank(results)}
    cache = args.cache.expanduser()
    cache.parent.mkdir(parents=True, exist_ok=True)
    history = json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else []
    history.append(report)
    cache.write_text(json.dumps(history[-20:], indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
