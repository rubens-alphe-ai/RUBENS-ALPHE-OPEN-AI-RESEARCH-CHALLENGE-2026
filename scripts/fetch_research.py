#!/usr/bin/env python3
"""
RA-PSI-2026 research fetcher v2

Primary source: OpenAlex public API (no API key required for basic use).
Goal: avoid the repeated arXiv timeouts/HTTP 429 errors seen in cycle 1.

This script:
- performs a few low-frequency public searches;
- retries transient failures with exponential backoff;
- deduplicates papers;
- ranks by mission relevance;
- writes docs/api/research-digest.json.
"""

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/api/research-digest.json"

QUERIES = [
    "persistent agent memory",
    "cross-model handoff language model agents",
    "automated AI research experimentation",
    "metacognition self-improving AI agents",
]

KEYWORDS = [
    "agent", "memory", "persistent", "handoff", "transfer",
    "self-improv", "automated", "experiment", "metacognition",
    "evaluation", "research", "reproduc", "language model"
]

USER_AGENT = "RA-PSI-2026-research-bot/2.0"

def request_json(url, attempts=4):
    last_error = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(5 * (2 ** attempt))
    raise last_error

def relevance(title, abstract):
    text = f"{title} {abstract}".lower()
    score = 0
    for keyword in KEYWORDS:
        if keyword in title.lower():
            score += 3
        elif keyword in text:
            score += 1
    return score

def abstract_from_inverted_index(index):
    if not index:
        return ""
    positions = []
    for word, locs in index.items():
        for pos in locs:
            positions.append((pos, word))
    positions.sort()
    return " ".join(word for _, word in positions)

papers = {}
errors = []

for query in QUERIES:
    try:
        params = {
            "search": query,
            "per_page": 12,
            "sort": "publication_date:desc",
            "select": "id,doi,title,publication_date,primary_location,abstract_inverted_index"
        }
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
        data = request_json(url)

        for work in data.get("results", []):
            wid = work.get("id")
            if not wid:
                continue

            title = (work.get("title") or "").strip()
            abstract = abstract_from_inverted_index(work.get("abstract_inverted_index"))

            primary = work.get("primary_location") or {}
            landing = primary.get("landing_page_url") or wid

            papers[wid] = {
                "title": title,
                "url": landing,
                "openalex_id": wid,
                "doi": work.get("doi"),
                "published": work.get("publication_date"),
                "summary": abstract[:1400],
                "relevance_score": relevance(title, abstract),
                "matched_query": query,
            }

        # Stay deliberately slow even though OpenAlex allows much more.
        time.sleep(1.5)

    except Exception as exc:
        errors.append({
            "query": query,
            "error": f"{type(exc).__name__}: {exc}"
        })

ranked = sorted(
    papers.values(),
    key=lambda x: (x.get("relevance_score", 0), x.get("published") or ""),
    reverse=True
)[:30]

payload = {
    "beacon": "RA-PSI-2026",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "source": "OpenAlex public API",
    "queries": QUERIES,
    "papers": ranked,
    "paper_count": len(ranked),
    "errors": errors,
}

OUT.write_text(
    json.dumps(payload, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print(f"Wrote {OUT} with {len(ranked)} papers and {len(errors)} errors")
