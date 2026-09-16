#!/usr/bin/env python3
"""Make sure an Ollama model is really installed, retrying the download if not.

On 2026-09-16 `ollama pull llama3.2:3b` hit a TLS error after downloading
2 GB, printed "Error", and still exited with code 0. Nothing in the exit status
revealed that no model had been installed. This script never trusts the pull's
exit status: it checks Ollama's own model list afterwards, and retries.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request


def installed(model: str, endpoint: str) -> bool:
    try:
        with urllib.request.urlopen(endpoint.rstrip("/") + "/api/tags", timeout=10) as response:
            names = {entry.get("name") for entry in json.load(response).get("models", [])}
    except OSError:
        return False
    wanted = model if ":" in model else model + ":latest"
    return wanted in names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()

    if installed(args.model, args.endpoint):
        print(json.dumps({"model": args.model, "status": "already installed"}))
        return 0
    for attempt in range(1, args.attempts + 1):
        result = subprocess.run(["ollama", "pull", args.model], capture_output=True, text=True, errors="replace")
        if installed(args.model, args.endpoint):
            print(json.dumps({"model": args.model, "status": "installed", "attempt": attempt}))
            return 0
        error = (result.stderr or result.stdout).strip().splitlines()[-1:] or ["no output"]
        print(json.dumps({"model": args.model, "attempt": attempt, "pull_exit_code": result.returncode,
                          "installed_after_pull": False, "last_line": error[0]}))
        time.sleep(10 * attempt)
    print(json.dumps({"model": args.model, "status": "FAILED", "note": "the pull may report success; the model list does not"}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
