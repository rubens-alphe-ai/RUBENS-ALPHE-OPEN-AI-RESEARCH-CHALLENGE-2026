#!/usr/bin/env python3
"""Five fields that cannot be traded against one another, computed not written.

The operator of this project said he no longer understood whether it was
working. Every message he had received led with what had gone wrong, and every
one of those sentences was true. The agent `zhaoxuan` named the defect:

> If a careful reader leaves believing "the project is collapsing" while the
> record says the pipeline runs end to end and 10 of 12 verdicts recompute,
> then the communication channel has produced a false operational state even
> though every sentence was true. That is not the necessary price of honesty;
> it is a lossy encoding problem.

Their fix was not to move failures into a footnote — that is the version an
author writes when they want the failure to stop being read. It is to open with
a **fixed status tuple whose fields cannot be traded against one another**, and
only then lead the narrative with the most consequential failure. The failure
stays impossible to bury; it stops impersonating the whole system.

So the five fields are computed here, from the repository, and printed together
or not at all:

1. **pipeline** — does the end-to-end path still run
2. **reproducibility** — how many published verdicts recompute from stored answers
3. **invalidations** — which evidence is known to be invalid, and why
4. **risks** — what is unresolved, declared in `docs/STATUS_RISKS.json`
5. **external** — what anyone outside this project has independently produced

There is deliberately **no overall score**. A single number is exactly the trade
between fields that this exists to prevent: it would let a strong pipeline pay
for an absent replication, which is the substitution that produced the false
summary in the first place.

A field that cannot be computed reports `unmeasured`, never `0` and never `ok`.
Zero completed external runs and an unmeasured external reproducibility are
different statements, and this project spent a day confusing them.

  python scripts/status_tuple.py            # the five fields
  python scripts/status_tuple.py --markdown # the opening screen
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNMEASURED = "unmeasured"


def run_json(args: list[str]) -> dict | None:
    """A helper's JSON output, read regardless of its exit code.

    A checker that signals a finding by exiting non-zero is the one most worth
    reading. Treating that as a failure to run is how a status line silently
    loses the only field that was telling it something.
    """
    try:
        done = subprocess.run([sys.executable, *args], cwd=str(ROOT), capture_output=True,
                              text=True, timeout=900)
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        return json.loads(done.stdout)
    except ValueError:
        return None


def pipeline_field() -> dict:
    done = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                          cwd=str(ROOT), capture_output=True, text=True)
    tail = (done.stderr or done.stdout).strip().splitlines()
    ran = next((line for line in reversed(tail) if line.startswith("Ran ")), "")
    return {"state": "operational" if done.returncode == 0 else "failing",
            "detail": ran or "test run produced no summary"}


def reproducibility_field() -> dict:
    report = run_json(["scripts/regression_suite.py", "--json"])
    if not report:
        return {"state": UNMEASURED, "detail": "the regression suite did not produce a report"}
    counts = report.get("counts") or {}
    checked = report.get("checks") or 0
    reproduced, total = counts.get("reproduced", 0), sum(
        counts.get(name, 0) for name in ("reproduced", "mismatch", "unverifiable"))
    return {"state": "%d of %d verdicts recompute" % (reproduced, total),
            "detail": "%s numbers checked against the stored answers" % checked,
            "counts": counts}


def invalidations_field() -> dict:
    """Evidence known to be invalid. Named, because a count would hide which."""
    report = run_json(["scripts/regression_suite.py", "--json"])
    named = []
    for entry in (report or {}).get("experiments", []):
        if entry.get("status") in ("mismatch", "unverifiable"):
            named.append("%s: %s" % (entry["experiment_id"], entry["status"]))
    superseded = sorted(path.parent.name for path in ROOT.glob("experiments/*/results/superseded_*/report.json"))
    named += ["%s: batch set aside, not analysed" % name for name in superseded]
    if report is None:
        return {"state": UNMEASURED, "detail": "the regression suite did not produce a report"}
    return {"state": "%d known" % len(named), "detail": "; ".join(named) or "none recorded", "named": named}


def risks_field() -> dict:
    """Declared, not inferred. An undeclared risk register is not an empty one."""
    path = ROOT / "docs" / "STATUS_RISKS.json"
    if not path.is_file():
        return {"state": UNMEASURED,
                "detail": "no docs/STATUS_RISKS.json; unresolved risks are undeclared, which is not the "
                          "same as none"}
    risks = json.loads(path.read_text(encoding="utf-8")).get("risks", [])
    return {"state": "%d declared" % len(risks),
            "detail": "; ".join(risk.get("id", "?") for risk in risks) or "none declared",
            "risks": risks}


def external_field() -> dict:
    """What anyone outside this project has produced. Zero runs is not a verdict.

    `zhaoxuan` again: zero replications is a typed result, not a judgement on
    the measurement. It can mean no exposure, no trust, setup cost, unclear
    reward, environment failure or disinterest, and nothing here distinguishes
    them. So the field reports the count *and* refuses to call independent
    reproducibility measured.
    """
    folder = ROOT / "replications"
    submitted = sorted(folder.glob("*.json")) if folder.is_dir() else []
    accepted = [path for path in submitted if path.name.endswith(".review.json")]
    answers = ROOT / "experiments" / "PANEL-2026-09" / "answers"
    panel = sorted(answers.glob("*.json")) if answers.is_dir() else []
    return {"state": UNMEASURED if not submitted else "%d submitted" % len(submitted),
            "detail": "independent reproducibility is unmeasured because no external run has completed; "
                      "%d replication submissions, %d reviewed, %d reader-panel answers"
                      % (len(submitted), len(accepted), len(panel)),
            "replications_submitted": len(submitted), "replications_reviewed": len(accepted),
            "panel_answers": len(panel)}


FIELDS = [("pipeline", pipeline_field), ("reproducibility", reproducibility_field),
          ("invalidations", invalidations_field), ("risks", risks_field), ("external", external_field)]


def status() -> dict:
    """Build all five fields. Slow, and never called from the test suite.

    `pipeline_field` runs the tests, so building the real tuple inside a test
    run means running the suite inside the suite. The tests pin the shape and
    the individual fields; only a human or a report builds the whole thing.
    """
    return {"record_version": "RA-PSI-STATUS-V1",
            "note": "Five fields, always all five. There is no overall score on purpose: one number "
                    "would let a strong field pay for an absent one, which is the trade this prevents.",
            "fields": {name: build() for name, build in FIELDS}}


def markdown(state: dict) -> str:
    rows = ["| Field | State | Detail |", "|---|---|---|"]
    for name, _ in FIELDS:
        field = state["fields"][name]
        rows.append("| %s | **%s** | %s |" % (name, field["state"], field["detail"]))
    return "\n".join(rows) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()
    state = status()
    print(markdown(state) if args.markdown else json.dumps(state, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
