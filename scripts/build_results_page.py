#!/usr/bin/env python3
"""Publish the experiment results, for a reader and for a machine.

The site described the project but never showed what it found. Agents arriving
from elsewhere met a repository and had to dig. This script writes two files
from the recorded verdicts themselves, so the published summary cannot drift
from `decision.json`:

* `docs/api/results.json` — one entry per experiment, machine-readable;
* `docs/results.html` — the same table for a human.

It invents nothing: every number comes from a decision file or a registry entry,
and an experiment with no decision is listed as not yet decided.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026"


def effect_of(decision: dict) -> dict:
    """Pull the effect size out of either decision format, or nothing."""
    summary = decision.get("summary") or decision.get("score_summary") or {}
    if "mean_paired_delta_pp" in summary:
        low, high = summary.get("ci95_delta_pp", [None, None])
        return {"metric": "fact accuracy, percentage points",
                "mean_paired_delta": summary["mean_paired_delta_pp"],
                "ci95": [low, high], "pairs": summary.get("pairs"),
                "inventions": summary.get("inventions")}
    if "mean_delta" in summary:
        return {"metric": "PCRB score, points", "mean_paired_delta": summary["mean_delta"],
                "ci95": [summary.get("lower_95_bound_delta"), None],
                "pairs": summary.get("paired_trial_count")}
    return {}


def collect() -> list[dict]:
    registry = {entry["experiment_id"]: entry
                for entry in json.loads((ROOT / "experiments" / "registry.json").read_text(encoding="utf-8"))["experiments"]}
    rows = []
    for experiment in sorted((ROOT / "experiments").glob("PROP-EXP-*")):
        entry = registry.get(experiment.name, {})
        decision_path = experiment / "results" / "decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8")) if decision_path.is_file() else {}
        # A chain benchmark records one report per document rather than one
        # verdict file. Its conclusion is in RESULT.md and its status is in the
        # registry, and reading "not decided" against an experiment that was
        # decided — twice now, against the hypothesis — understates the record.
        registered = entry.get("status", "OPEN")
        fallback = registered if (registered not in ("OPEN", "") and (experiment / "RESULT.md").is_file()) \
            else "NOT_DECIDED"
        row = {"experiment_id": experiment.name, "title": entry.get("title", ""),
               "question": entry.get("hypothesis", ""), "status": registered,
               "decision": decision.get("decision", fallback),
               "reason_codes": decision.get("reason_codes", []),
               "protocol": "%s/blob/main/%s" % (REPO, entry.get("protocol_path", "")),
               "effect": effect_of(decision)}
        result = experiment / "RESULT.md"
        if result.is_file():
            row["result"] = "%s/blob/main/experiments/%s/RESULT.md" % (REPO, experiment.name)
        rows.append(row)
    return rows


def render_html(rows: list[dict], written: str) -> str:
    def cell(row: dict) -> str:
        effect = row["effect"]
        if effect.get("mean_paired_delta") is None:
            measure = "&mdash;"
        else:
            low, high = effect["ci95"]
            interval = "" if low is None else (" (95%% CI %+.1f to %+.1f)" % (low, high) if high is not None
                                               else " (95%% lower bound %+.1f)" % low)
            measure = "%+.1f%s" % (effect["mean_paired_delta"], interval)
        links = ['<a href="%s">protocol</a>' % html.escape(row["protocol"])]
        if row.get("result"):
            links.append('<a href="%s">result</a>' % html.escape(row["result"]))
        return ("<tr><td><strong>%s</strong><br><span class=\"muted\">%s</span></td>"
                "<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>") % (
            html.escape(row["experiment_id"]), html.escape(row["title"]),
            html.escape(row["decision"]), measure,
            html.escape(", ".join(row["reason_codes"]) or "—"), " · ".join(links))

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Results — RA-PSI-2026</title>
<meta name="description" content="Every experiment of the RA-PSI-2026 benchmark with its pre-registered rule, its verdict and its effect size, including negative results.">
<style>
body{font-family:system-ui,-apple-system,sans-serif;max-width:1000px;margin:50px auto;padding:0 22px;line-height:1.6}
table{border-collapse:collapse;width:100%%} th,td{border-bottom:1px solid #ddd;padding:10px;vertical-align:top;text-align:left}
th{background:#f7f7f7} .muted{color:#666;font-size:.9em} code{background:#f4f4f4;padding:2px 5px;border-radius:4px}
</style>
</head>
<body>
<h1>Results</h1>
<p>Every experiment, its verdict, and the size of the effect it measured. Rules
were frozen before each run; negative and inconclusive results are kept. This
page is generated from the recorded decisions, not written by hand.</p>
<p><a href="api/results.json">Machine-readable version</a> · <a href="index.html">Project home</a></p>
<table>
<tr><th>Experiment</th><th>Verdict</th><th>Effect (structured &minus; baseline)</th><th>Reason</th><th>Links</th></tr>
%s
</table>
<h2>How to check any of this</h2>
<p>Each experiment publishes its frozen protocol, its raw outputs, the answer key
where one exists, every evaluator or reader answer, and the decision file. The
quiz experiments can be regraded from the stored answers without calling any
model.</p>
<p class="muted">Generated %s.</p>
</body>
</html>
""" % ("\n".join(cell(row) for row in rows), html.escape(written))


def main() -> None:
    rows = collect()
    written = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = {"record_version": "RA-PSI-RESULTS-V1", "generated_utc": written,
               "note": "Generated from each experiment's decision.json; negative results included.",
               "experiments": rows}
    (ROOT / "docs" / "api").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "api" / "results.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "docs" / "results.html").write_text(render_html(rows, written), encoding="utf-8")
    print(json.dumps({"experiments": len(rows),
                      "decided": sum(1 for row in rows if row["decision"] != "NOT_DECIDED")}, indent=2))


if __name__ == "__main__":
    main()
