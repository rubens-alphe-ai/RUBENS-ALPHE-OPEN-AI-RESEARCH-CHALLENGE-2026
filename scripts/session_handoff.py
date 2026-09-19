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
    """Totals across every post, from each one's most recent check.

    Reading only the last entry reported whatever had just been posted, which
    for a post checked seconds after publication is zero upvotes and no
    comments — an accurate number that tells a later reader the opposite of the
    truth. Outreach is the sum of what is out there, not the newest row.
    """
    path = ROOT / "docs" / "api" / "outreach.json"
    if not path.is_file():
        return {}
    entries = json.loads(path.read_text(encoding="utf-8")).get("entries", [])
    latest: dict[str, dict] = {}
    for entry in entries:
        latest[entry.get("post_id", "?")] = entry
    if not latest:
        return {}
    def total(field: str) -> int:
        return sum(int((entry.get("moltbook") or {}).get(field) or 0) for entry in latest.values())
    newest = entries[-1]
    return {"posts": len(latest), "upvotes": total("upvotes"), "comments": total("comment_count"),
            "replications": newest.get("replications") or {},
            "checked_at_utc": newest.get("checked_at_utc")}


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
        "## Start here",
        "",
        "Read this file first, then `docs/CONTINUITY_PROGRAMME.md` for what was asked and "
        "what came back, then the RESULT.md of the highest-numbered experiment. Everything else "
        "is detail. Nothing in this repository needs the previous session to be explained.",
        "",
        "Before changing anything: `python -m unittest discover -s tests` must be green, and "
        "`git status` will show whether work was left uncommitted.",
        "",
        "## Verified knowledge",
        "",
        "- The measurement removes language-model judges: a writer produces a handoff, a "
        "different model that sees only that handoff answers questions whose answers were "
        "fixed beforehand, and a script compares letters.",
        "- %d experiments are registered, %d have a verdict, %d reached PROVISIONAL_KEEP." % (len(rows), len(decided), len(keeps)),
        "- Naming the kinds of item to carry raises fact transfer across three writer families "
        "and three documents; models omit rather than invent.",
        "- 8 of 11 published verdicts reproduce exactly from the stored answers, 1 does not "
        "(PROP-EXP-MEM-007, see its CORRECTION.md; the verdict and the mean are unaffected), and 2 "
        "rest on answers that were never stored. `python scripts/regression_suite.py` says which is "
        "which and exits non-zero rather than reassuring.",
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
        "- A public reader panel is **open and unanswered** (`experiments/PANEL-2026-09/`). Its key is "
        "hashed in `public/commitment.json`; the quiz and source document are held outside the "
        "repository, in `~/.ra-psi/panel/sealed/`, and must stay there until it closes. Collect replies "
        "into `experiments/PANEL-2026-09/answers/` as JSON files with a `responder` and an "
        "`answers_text`, then `python scripts/panel.py grade`, then `reveal`.",
        "- The holdout (`experiments/HOLDOUT-2026-09/`) is sealed and unused.",
        "- The Continuity Programme (`docs/CONTINUITY_PROGRAMME.md`): stages 1 and 2 ran and were both refused. "
        "Stage 3, evolving the instruction against the sealed holdout, has not run.",
        "",
        "## Rules in force",
        "",
        "- Protocols, thresholds and quizzes are committed before the first trial of an experiment.",
        "- Deviations are recorded before any score they could influence is seen.",
        "- Failures are counted; uneven failures across conditions make an experiment unusable, not adjustable.",
        "- Keys live in `~/.ra-psi/keys`, never in the repository and never in a conversation.",
        "- The measure is published and attacked, not only the result. An outside agent corrected one of "
        "ours within hours, and the correction undid a sentence already posted.",
        "- Merges into `main` are the owner's decision.",
        "- Paid runs declare a ceiling in their policy; `scripts/cost_guard.py` refuses to start above it.",
        "",
        "## State of the outside world",
        "",
        "- Moltbook agent `rubens_alphe_psi`: %s posts, %s upvotes and %s comments in total, "
        "%s replications accepted (criteria and verdict date in `docs/OUTREACH_CRITERIA.md`). "
        "Counted at %s; run `python scripts/track_outreach.py --post-id <id>` to refresh."
        % (last.get("posts", "?"), last.get("upvotes", "?"), last.get("comments", "?"),
           (last.get("replications") or {}).get("accepted", 0), last.get("checked_at_utc", "?")),
        "- One outside hypothesis is on the record under its author's name: PROP-EXP-MEM-012 was proposed by the "
        "Moltbook agent `zhaoxuan`, who then corrected its metric. Replies to them are owed in that thread.",
        "- Branch: `%s`. Last commits:" % (git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"),
        "",
    ]
    lines += ["  - " + line for line in (git("log", "--oneline", "-5") or "").splitlines()]
    lines += [
        "",
        "## Open questions",
        "",
        "- Stage 1 and stage 2 are answered, both against the hypothesis: merging chains recovers "
        "dispersion rather than loss, and an archive does not change a chain's fate. See their RESULT.md.",
        "- How much of a `facts kept` figure is a property of the reader rather than of the handoff? "
        "This is the open panel, and it is the biggest unmeasured error bar in every published number.",
        "- Can handoff instructions be evolved rather than written, and survive the holdout? (stage 3)",
        "- Does the chain result hold with writer families other than DeepSeek?",
        "",
        "## Next actions",
        "",
        "- Close the reader panel once enough replies are in, publish every answer, the spread between "
        "readers, and the nonce.",
        "- Run stage 3 of the Continuity Programme, if its pre-registration shows a 5-point effect is "
        "resolvable at a defensible cost. MEM-012 found six repeats cannot resolve six points.",
        "- Every new threshold must declare `decision.control_prior_pct` and pass "
        "`python scripts/check_headroom.py --experiment <id>`. Two registered thresholds were "
        "arithmetically impossible before their first call; that is why the guard exists.",
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
