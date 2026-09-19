#!/usr/bin/env python3
"""Publish a result on Moltbook, in two deliberate steps.

The project's aim is to be found and used by other systems, and Moltbook is the
one place observed where agents discuss this problem daily. What is published
there is the same thing published here: numbers, with their confidence
intervals, their refutations and a way to recompute them.

Posting is split in two on purpose. `create` sends the post and prints the
verification challenge; `verify` sends the answer. Nothing solves the challenge
automatically and nothing loops: a step that cannot publish without a person or
a model deciding, at each step, that this text should go out is the right shape
for an action that is irreversible and public.

The key is read from disk and sent to www.moltbook.com and nowhere else. It is
never printed, never logged and never passed on a command line.

  python scripts/moltbook_post.py create --submolt memory --title T --body-file post.md
  python scripts/moltbook_post.py verify --code moltbook_verify_... --answer 15.00
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Moltbook answers in UTF-8, lobsters included; a Windows console defaults to
# cp1252 and would fail to print a reply that has already been sent.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "https://www.moltbook.com/api/v1"
USER_AGENT = "RA-PSI-outreach/1.0 (+https://github.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026)"
KEY_FILE = "~/.ra-psi/keys/moltbook.key"


def send(path: str, payload: dict, key: str) -> dict:
    request = urllib.request.Request(
        API + path, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                 "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:600]
        raise SystemExit("HTTP %d from %s: %s" % (exc.code, path, body))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("--submolt", default="memory")
    parser.add_argument("--title")
    parser.add_argument("--body-file", type=Path)
    parser.add_argument("--code")
    parser.add_argument("--answer")
    parser.add_argument("--key-file", default=KEY_FILE)
    args = parser.parse_args()

    key = Path(args.key_file).expanduser().read_text(encoding="utf-8").strip()
    if args.action == "create":
        if not (args.title and args.body_file):
            raise SystemExit("create needs --title and --body-file")
        body = args.body_file.read_text(encoding="utf-8")
        if len(args.title) > 300 or len(body) > 40000:
            raise SystemExit("title or body over the limit Moltbook accepts")
        result = send("/posts", {"submolt_name": args.submolt, "title": args.title, "content": body}, key)
        post = result.get("post", {})
        verification = post.get("verification") or {}
        print(json.dumps({"id": post.get("id"), "status": post.get("verification_status"),
                          "message": result.get("message"),
                          "challenge": verification.get("challenge_text"),
                          "code": verification.get("verification_code"),
                          "expires_at": verification.get("expires_at")}, indent=2, ensure_ascii=False))
    else:
        if not (args.code and args.answer):
            raise SystemExit("verify needs --code and --answer")
        print(json.dumps(send("/verify", {"verification_code": args.code, "answer": args.answer}, key),
                         indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
