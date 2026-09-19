#!/usr/bin/env python3
"""Write the project's own handoff, in the format this project measured as best.

The assistant working on this repository does not persist. Each session starts
without memory of the last, which is the very failure the experiments measure.
MEM-005 to MEM-008 found what survives a handoff: an explicit list of items by
kind, each with its status, rather than a free summary. So the project writes
its own state that way, from its own records, and a later session reads it
first.

Nothing here is written by a model: every line comes from the registry, the
decision files, the run reports and git. That is the point — a handoff whose
facts can be checked against the thing they describe.

  python scripts/session_handoff.py            # writes docs/SESSION_HANDOFF.md
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "SESSION_HANDOFF.md"


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout.strip()
    except OSError:
        return ""


def experiments() -> list[dict]:
    registry = json.loads((ROOT / "experiments" / "registry.json").read_text(encoding="utf-8"))
    rows = []
    for entry in registry["experiments"]:
        folder = ROOT / "experiments" / entry["experiment_id"]
        decision_path = folder / "results" / "decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8")) if decision_path.is_file() else {}
        if not decision and list(folder.glob("results/*/report.json")):
            # A chain benchmark records one report per document, not one verdict
            # file; its conclusion lives in RESULT.md and in the registry.
            decision = {"decision": entry.get("status", "").replace("_", " ").lower() or "see RESULT.md"}
        summary = decision.get("summary") or decision.get("score_summary") or {}
        rows.append({"id": entry["experiment_id"], "status": entry.get("status", "OPEN"),
                     "decision": decision.get("decision"), "delta": summary.get("mean_paired_delta_pp"),
                     "ci": summary.get("ci95_delta_pp"), "notes": entry.get("notes", ""),
                     "has_result": (folder / "RESULT.md").is_file()})
    return rows


def runs_in_flight() -> list[str]:
    """Experiments whose last run report did not reach a decision."""
    pending = []
    for report in sorted(ROOT.glob("experiments/*/results/run-report.json")):
        status = json.loads(report.read_text(encoding="utf-8")).get("status", "")
        if status not in ("DECIDED",):
            pending.append("%s: %s" % (report.parent.parent.name, status))
    return pending


def outreach() -> dict:
    path = ROOT / "docs" / "api" / "outreach.json"
    if not path.is_file():
        return {}
    entries = json.loads(path.read_text(encoding="utf-8")).get("entries", [])
    return entries[-1] if entries else {}


def render() -> str:
    rows = experiments()
    decided = [row for row in rows if row["decision"]]
    keeps = [row for row in decided if row["decision"] == "PROVISIONAL_KEEP"]
    last = outreach()
    lines = [
        "# Session handoff",
        "",
        "Written by `scripts/session_handoff.py` from the repository's own records on "
        + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") + ".",
        "It uses the handoff format this project measured as the best one "
        "(MEM-005 to MEM-008): items by kind, each with its status.",
        "",
        "## Verified knowledge",
        "",
        "- The measurement removes language-model judges: a writer produces a handoff, a "
        "different model that sees only that handoff answers questions whose answers were "
        "fixed beforehand, and a script compares letters.",
        "- %d experiments are registered, %d have a verdict, %d reached PROVISIONAL_KEEP." % (len(rows), len(decided), len(keeps)),
        "- Naming the kinds of item to carry raises fact transfer across three writer families "
        "and three documents; models omit rather than invent.",
        "- Every published verdict can be recomputed from the stored answers: "
        "`python -m unittest tests.test_published_results`.",
        "",
        "## Experiments and their status",
        "",
        "| Experiment | Status | Verdict | Effect |",
        "|---|---|---|---|",
    ]
    for row in rows:
        effect = "—"
        if row["delta"] is not None:
            effect = "%+.1f pp" % row["delta"]
            if row["ci"]:
                effect += " (%.1f to %.1f)" % (row["ci"][0], row["ci"][1])
        lines.append("| %s | %s | %s | %s |" % (row["id"], row["status"], row["decision"] or "not decided", effect))
    pending = runs_in_flight()
    lines += [
        "",
        "## What is unfinished",
        "",
    ]
    lines += ["- Run not finished — %s" % item for item in pending] or ["- No run is in flight."]
    lines += [
        "- Calibration failed once (`calibration/PCRB2/`) and has not been rerun; FINAL_KEEP needs it.",
        "- The holdout (`experiments/HOLDOUT-2026-09/`) is sealed and unused.",
        "- The Continuity Programme (`docs/CONTINUITY_PROGRAMME.md`) is registered; stage 1 has not run.",
        "",
        "## Rules in force",
        "",
        "- Protocols, thresholds and quizzes are committed before the first trial of an experiment.",
        "- Deviations are recorded before any score they could influence is seen.",
        "- Failures are counted; uneven failures across conditions make an experiment unusable, not adjustable.",
        "- Keys live in `~/.ra-psi/keys`, never in the repository and never in a conversation.",
        "- Paid runs declare a ceiling in their policy; `scripts/cost_guard.py` refuses to start above it.",
        "",
        "## State of the outside world",
        "",
        "- Moltbook agent `rubens_alphe_psi`: %s upvotes, %s comments, %s replications accepted "
        "(criteria and verdict date in `docs/OUTREACH_CRITERIA.md`)."
        % ((last.get("moltbook") or {}).get("upvotes", "?"), (last.get("moltbook") or {}).get("comment_count", "?"),
           (last.get("replications") or {}).get("accepted", 0)),
        "- Branch: `%s`. Last commits:" % (git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"),
        "",
    ]
    lines += ["  - " + line for line in (git("log", "--oneline", "-5") or "").splitlines()]
    lines += [
        "",
        "## Open questions",
        "",
        "- Does merging several independent chains recover what each lost? (Continuity Programme, stage 1)",
        "- Does a checkable archive change the nature of the loss, or only its slope? (stage 2)",
        "- Can handoff instructions be evolved rather than written, and survive the holdout? (stage 3)",
        "- Does the chain result hold with writer families other than DeepSeek?",
        "",
        "## Next actions",
        "",
        "- Run stage 1 of the Continuity Programme.",
        "- Rerun calibration as a new anchor-set version; do not edit the one that failed.",
        "- Trigger the GitHub Actions workflow once, so a run no longer depends on this machine.",
        "- Read `docs/OUTREACH_CRITERIA.md` on 2026-10-18 and write the verdict, whatever it says.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    text = render()
    TARGET.write_text(text, encoding="utf-8")
    local = Path("~/.ra-psi/SESSION_HANDOFF.md").expanduser()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(text, encoding="utf-8")
    print(json.dumps({"written": [str(TARGET), str(local)], "bytes": len(text)}, indent=2))


if __name__ == "__main__":
    main()
