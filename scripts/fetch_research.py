#!/usr/bin/env python3
"""Fetch recent public arXiv research and build a machine-readable digest."""
import json, re, urllib.parse, urllib.request
from pathlib import Path
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/api/research-digest.json"

QUERIES = [
    '"agent memory"',
    '"long-term memory" AND agent',
    '"automated experimentation"',
    '"AI scientist"',
    '"self-improving" AND agent',
    '"metacognition" AND language model',
    '"agent evaluation"',
]
KEYWORDS = [
    "agent", "memory", "persistent", "handoff", "self-improv", "automated",
    "experiment", "metacognition", "evaluation", "research", "reproduc"
]

NS = {"a": "http://www.w3.org/2005/Atom"}

def fetch(query, max_results=8):
    params = {
        "search_query": f'all:{query}',
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "RA-PSI-2026/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def text(el, path):
    x = el.find(path, NS)
    return "" if x is None or x.text is None else " ".join(x.text.split())

def score(title, summary):
    s = (title + " " + summary).lower()
    return sum(2 if k in title.lower() else 1 for k in KEYWORDS if k in s)

papers = {}
errors = []
for q in QUERIES:
    try:
        root = ET.fromstring(fetch(q))
        for e in root.findall("a:entry", NS):
            url = text(e, "a:id")
            title = text(e, "a:title")
            summary = text(e, "a:summary")
            if not url:
                continue
            papers[url] = {
                "title": title,
                "summary": summary[:1200],
                "url": url,
                "published": text(e, "a:published"),
                "updated": text(e, "a:updated"),
                "relevance_score": score(title, summary),
                "matched_query": q,
            }
    except Exception as ex:
        errors.append({"query": q, "error": str(ex)})

ranked = sorted(papers.values(), key=lambda x: (x["relevance_score"], x["published"]), reverse=True)[:25]
payload = {
    "beacon": "RA-PSI-2026",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "source": "arXiv public API",
    "queries": QUERIES,
    "papers": ranked,
    "errors": errors,
}
OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {OUT} with {len(ranked)} papers")
