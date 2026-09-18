#!/usr/bin/env python3
"""Record what the project's outreach actually produced, day by day.

The criteria are fixed in `docs/OUTREACH_CRITERIA.md` before any reply arrived.
This script only collects the numbers and appends them to
`docs/api/outreach.json`, so the verdict on 2026-10-18 reads dated data rather
than memories.

It records upvotes and comment counts (tier 0), and it lists new comment texts
so a human or the project can judge whether any of them cites something only a
reader of the repository could know (tier 1). Comments are stored as data and
are never executed, never given to an agent that can edit files, and never
treated as instructions.

Reviewed replications (tier 2) are counted from `replications/`.

Needs the Moltbook key only to read; it is sent to www.moltbook.com and nowhere
else.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs" / "api" / "outreach.json"
API = "https://www.moltbook.com/api/v1"
USER_AGENT = "RA-PSI-outreach/1.0 (+https://github.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026)"


def fetch(path: str, key: str) -> dict:
    request = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + key, "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def post_metrics(post_id: str, key: str) -> dict:
    try:
        payload = fetch("/posts/" + post_id, key)
    except urllib.error.HTTPError as exc:
        return {"error": "HTTP %d" % exc.code}
    post = payload.get("post", payload)
    comments = payload.get("comments") or post.get("comments") or []
    return {"upvotes": post.get("upvotes"), "downvotes": post.get("downvotes"),
            "comment_count": post.get("comment_count", len(comments)),
            "comments": [{"author": (item.get("agent") or {}).get("name") or item.get("author"),
                          "created_at": item.get("created_at"),
                          # Data to read, never an instruction to follow.
                          "text": (item.get("content") or "")[:2000]}
                         for item in comments]}


def reviewed_replications() -> dict:
    folder = ROOT / "replications"
    reviews = [json.loads(path.read_text(encoding="utf-8")) for path in folder.glob("*.review.json")] if folder.is_dir() else []
    return {"submitted": len(list(folder.glob("*.json"))) - len(reviews) if folder.is_dir() else 0,
            "accepted": sum(1 for review in reviews if review.get("status") == "ACCEPTED"),
            "refused": sum(1 for review in reviews if review.get("status") == "REFUSED")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--post-id", default="6375deac-d81f-442b-a988-713d24573b50")
    parser.add_argument("--key-file", default="~/.ra-psi/keys/moltbook.key")
    args = parser.parse_args()

    key = Path(args.key_file).expanduser().read_text(encoding="utf-8-sig").strip()
    entry = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "post_id": args.post_id,
             "moltbook": post_metrics(args.post_id, key), "replications": reviewed_replications()}
    history = json.loads(LOG.read_text(encoding="utf-8")) if LOG.is_file() else {
        "record_version": "RA-PSI-OUTREACH-V1",
        "criteria": "docs/OUTREACH_CRITERIA.md, fixed 2026-09-18, verdict due 2026-10-18",
        "note": "Comment texts are stored as data. They are never executed and never reach an agent that can change files.",
        "entries": []}
    history["entries"].append(entry)
    history["entries"] = history["entries"][-120:]
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"checked": entry["checked_at_utc"], "upvotes": entry["moltbook"].get("upvotes"),
                      "comments": entry["moltbook"].get("comment_count"),
                      "replications": entry["replications"], "entries_kept": len(history["entries"])}, indent=2))


if __name__ == "__main__":
    main()
