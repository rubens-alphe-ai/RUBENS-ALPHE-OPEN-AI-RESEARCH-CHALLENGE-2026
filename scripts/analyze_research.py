#!/usr/bin/env python3
"""
RA-PSI-2026 Research Assessor v1

Purpose:
- read docs/api/research-digest.json
- flag suspicious metadata (e.g. future publication dates)
- rank papers by practical relevance to RA-PSI
- detect dominant research themes
- propose ONE measurable next experiment
- write docs/api/research-assessment.json
- write docs/api/proposed-next-problem.json

This script does not replace the canonical NEXT_UNSOLVED_PROBLEM automatically.
It proposes a candidate that must be evaluated/accepted first.
"""

import json
from collections import Counter
from datetime import datetime, timezone, date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIGEST = ROOT / "docs/api/research-digest.json"
ASSESSMENT = ROOT / "docs/api/research-assessment.json"
PROPOSED = ROOT / "docs/api/proposed-next-problem.json"

THEMES = {
    "persistent_memory": [
        "memory", "persistent", "long-term", "long term", "episodic", "state"
    ],
    "cross_model_handoff": [
        "handoff", "transfer", "cross-model", "cross model", "inter-model",
        "inter model", "model transfer"
    ],
    "automated_experimentation": [
        "experiment", "automated research", "ai scientist", "scientist",
        "self-improving", "self improving"
    ],
    "metacognition": [
        "metacognition", "self-evaluation", "self evaluation",
        "reflection", "calibration", "uncertainty"
    ],
    "agent_evaluation": [
        "evaluation", "benchmark", "reproducibility", "reproducible",
        "agent evaluation"
    ],
}

def parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None

def theme_hits(text):
    text = text.lower()
    scores = {}
    for theme, words in THEMES.items():
        scores[theme] = sum(1 for w in words if w in text)
    return scores

def quality_score(paper, today):
    title = paper.get("title") or ""
    summary = paper.get("summary") or ""
    base = int(paper.get("relevance_score") or 0)

    score = base
    reasons = []

    if len(summary) >= 300:
        score += 2
        reasons.append("substantial abstract")
    elif len(summary) < 80:
        score -= 2
        reasons.append("very short abstract")

    published = parse_date(paper.get("published"))
    if published and published > today:
        score -= 8
        reasons.append("future publication date flagged")

    hits = theme_hits(title + " " + summary)
    theme_total = sum(hits.values())
    score += min(theme_total, 6)

    if paper.get("doi"):
        score += 1

    return score, reasons, hits

data = json.loads(DIGEST.read_text(encoding="utf-8"))
today = datetime.now(timezone.utc).date()

ranked = []
theme_counter = Counter()
anomalies = []

for paper in data.get("papers", []):
    score, reasons, hits = quality_score(paper, today)
    for theme, n in hits.items():
        theme_counter[theme] += n

    item = {
        "title": paper.get("title"),
        "url": paper.get("url"),
        "published": paper.get("published"),
        "original_relevance_score": paper.get("relevance_score"),
        "assessment_score": score,
        "matched_query": paper.get("matched_query"),
        "theme_hits": hits,
        "notes": reasons,
    }

    pub = parse_date(paper.get("published"))
    if pub and pub > today:
        anomalies.append({
            "type": "future_publication_date",
            "title": paper.get("title"),
            "published": paper.get("published"),
            "url": paper.get("url"),
        })

    ranked.append(item)

ranked.sort(key=lambda x: x["assessment_score"], reverse=True)
top = ranked[:5]

dominant_theme = theme_counter.most_common(1)[0][0] if theme_counter else "persistent_memory"

EXPERIMENTS = {
    "persistent_memory": {
        "id": "PROP-EXP-MEM-001",
        "title": "Structured Memory Handoff Test",
        "hypothesis": (
            "Separating project memory into decisions, failures, verified knowledge, "
            "open questions, and next actions will improve blind handoff fidelity."
        ),
        "metric": "PCRB-1 handoff score and critical-fabrication count",
        "procedure": [
            "Create a structured-state representation with five explicit memory sections.",
            "Give the same mission to fresh models using current state vs structured state.",
            "Run at least three blind handoff trials per condition.",
            "Compare average PCRB-1 score and fabrication rate.",
        ],
        "success": ">= 10-point PCRB-1 improvement with zero increase in critical fabrications",
    },
    "cross_model_handoff": {
        "id": "PROP-EXP-HANDOFF-001",
        "title": "Cross-Model Transfer Robustness",
        "hypothesis": (
            "A provider-neutral handoff schema will reduce information loss across unrelated models."
        ),
        "metric": "mission reconstruction fidelity across >=3 unrelated model families",
        "procedure": [
            "Freeze one canonical state snapshot.",
            "Send only the public manifest + state to three unrelated model families.",
            "Score outputs with PCRB-1.",
            "Identify fields most often lost or fabricated.",
        ],
        "success": ">=90/100 median PCRB-1 with zero critical fabrications",
    },
    "automated_experimentation": {
        "id": "PROP-EXP-AUTO-001",
        "title": "Hypothesis-to-Experiment Reliability",
        "hypothesis": (
            "Requiring a predefined metric before implementation will reduce low-value experiments."
        ),
        "metric": "fraction of experiments reaching a valid KEEP/REJECT decision",
        "procedure": [
            "Collect 10 proposed experiments.",
            "Require hypothesis, baseline, metric, stopping rule before execution.",
            "Run the experiments in a sandbox.",
            "Measure how many produce an interpretable decision.",
        ],
        "success": ">=80% of experiments yield a reproducible KEEP/REJECT decision",
    },
    "metacognition": {
        "id": "PROP-EXP-META-001",
        "title": "Calibration Before Action",
        "hypothesis": (
            "Recording confidence before each research action will improve error detection and calibration."
        ),
        "metric": "Brier score + failure-prediction accuracy",
        "procedure": [
            "Before each of 20 tasks, record probability of success.",
            "Execute tasks unchanged.",
            "Compare predictions with outcomes.",
            "Use calibration error to adjust future confidence.",
        ],
        "success": "measurable calibration improvement over two consecutive batches",
    },
    "agent_evaluation": {
        "id": "PROP-EXP-EVAL-001",
        "title": "Evaluator Independence Test",
        "hypothesis": (
            "Separating proposer and evaluator roles will reduce false improvement claims."
        ),
        "metric": "false-positive acceptance rate on seeded bad proposals",
        "procedure": [
            "Create a mixed set of valid and intentionally flawed improvement proposals.",
            "Have one agent propose and a separate evaluator score them.",
            "Measure acceptance of flawed proposals.",
            "Compare with self-evaluation baseline.",
        ],
        "success": ">=50% reduction in false-positive acceptance rate",
    },
}

proposal = EXPERIMENTS.get(dominant_theme, EXPERIMENTS["persistent_memory"])

assessment = {
    "beacon": "RA-PSI-2026",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "source_digest_generated_at_utc": data.get("generated_at_utc"),
    "paper_count_seen": len(data.get("papers", [])),
    "dominant_theme": dominant_theme,
    "theme_counts": dict(theme_counter),
    "top_5_papers": top,
    "metadata_anomalies": anomalies,
    "proposed_next_experiment": proposal,
    "decision_rule": (
        "This is a proposal only. Canonical state changes only after evaluation/acceptance."
    ),
}

ASSESSMENT.write_text(
    json.dumps(assessment, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

proposed_problem = {
    "status": "PROPOSED",
    "generated_at_utc": assessment["generated_at_utc"],
    "derived_from_theme": dominant_theme,
    **proposal,
}
PROPOSED.write_text(
    json.dumps(proposed_problem, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print(f"Wrote {ASSESSMENT}")
print(f"Wrote {PROPOSED}")
print(f"Dominant theme: {dominant_theme}")
print(f"Flagged anomalies: {len(anomalies)}")
