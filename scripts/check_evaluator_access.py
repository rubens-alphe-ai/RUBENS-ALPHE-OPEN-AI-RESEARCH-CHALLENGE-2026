#!/usr/bin/env python3
"""Check that every configured evaluator is reachable, before any evaluation runs.

For each scorer and checker in the configuration, this script verifies three
things, without ever printing or storing a key:

1. its key file exists and is not empty (only the length is reported);
2. the provider accepts the key (its OpenAI-compatible ``/models`` endpoint);
3. the configured model name is one the provider actually serves.

When the model name is wrong, it lists close matches from the provider's own
catalogue, so a model name never has to be guessed from memory or from an
out-of-date example.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def models_url(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    for suffix in ("/chat/completions", "/completions"):
        if base.endswith(suffix):
            return base[: -len(suffix)] + "/models"
    return base + "/models"


def check(entry: dict) -> dict:
    result = {"evaluator_id": entry["evaluator_id"], "provider": entry["provider"], "model": entry["model"]}
    key_path = Path(entry["api_key_file"]).expanduser()
    if not key_path.is_file():
        return {**result, "status": "NO_KEY_FILE", "key_file": str(key_path)}
    key = key_path.read_text(encoding="utf-8-sig").strip()
    if not key:
        return {**result, "status": "EMPTY_KEY_FILE", "key_file": str(key_path)}
    result["key_length"] = len(key)

    request = urllib.request.Request(models_url(entry["endpoint"]), headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        status = "KEY_REJECTED" if exc.code in (401, 403) else "HTTP_%d" % exc.code
        return {**result, "status": status}
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        return {**result, "status": "UNREACHABLE", "error": str(exc)[:200]}

    available = sorted({str(item.get("id", "")) for item in payload.get("data", []) if isinstance(item, dict)})
    # Some providers prefix ids (for example "models/gemini-..."); accept both forms.
    normalised = {name.split("/", 1)[1] if name.startswith("models/") else name for name in available}
    if entry["model"] in available or entry["model"] in normalised:
        return {**result, "status": "OK"}
    return {**result, "status": "MODEL_NOT_SERVED",
            "closest_available": difflib.get_close_matches(entry["model"], sorted(normalised), n=5, cutoff=0.3),
            "catalogue_size": len(available)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.expanduser().read_text(encoding="utf-8"))
    results = [check(entry) for role in ("scorers", "checkers") for entry in config.get(role, [])]
    ready = [r["evaluator_id"] for r in results if r["status"] == "OK"]
    print(json.dumps({"results": results, "ready": ready,
                      "scorers_ready": sum(1 for e in config.get("scorers", []) if e["evaluator_id"] in ready),
                      "checkers_ready": sum(1 for e in config.get("checkers", []) if e["evaluator_id"] in ready)},
                     indent=2, ensure_ascii=False))
    return 0 if len(ready) == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
