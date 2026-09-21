#!/usr/bin/env python3
"""Fail a build when a change quietly destroyed more of what the handover carried.

A measurement delivered as a report is read once and is then out of date; this
project caught one of its own published numbers drifting within hours. A check
that fails a pull request keeps being true. So this is the same measurement as
`handoff_bench`, pointed at a recorded baseline instead of at a reader.

It compares a fresh `report.json` against a baseline written from an earlier one
and fails when fact retention has dropped past a declared margin, when the run
invented anything it did not invent before, or when the run is **unusable**
under `handoff_bench.usability` — an unusable run is not "no regression
detected", because absence of a result is not absence of a regression.

**It refuses to fail on noise, and this is the hard part.** Two identical runs
of the same arm in this project gave +3.6/+5.6/+3.5 and +10.9/+2.8/+11.8: the
same measurement of the same thing, differing by up to 8 points. A gate that
fired on that would be switched off inside a week, and a switched-off gate is
worth nothing. So the baseline records its repeat count and its observed spread,
and a drop is only a regression when it clears **both** the declared margin and
the run-to-run noise floor of the two runs being compared. Every verdict states
the smallest drop it could have detected, whether it fired or not — because a
gate that passes silently while being blind to a ten-point regression is lying
by omission, and that is a fact about the product the buyer should be told on
every run rather than after their incident.

Exit codes follow this project's discipline: 0 the gate passes, 1 a real
regression, 2 it cannot tell. "We could not measure it" must never report as "it
checks out", so an unusable run, a missing arm, and a baseline recorded on
different material all exit 2 and fail the build without claiming a finding.

  python scripts/ci_gate.py --baseline gate-baseline.json --report bench/report.json
  python scripts/ci_gate.py --report bench/report.json --arm checklist --hop 5 \\
      --document clinic.md --quiz clinic-quiz.json --write-baseline gate-baseline.json

This script makes no model calls of its own. It reads two files that a benchmark
run already wrote.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import handoff_bench as hb  # noqa: E402
from handoff_quiz import T_975  # noqa: E402

RECORD_VERSION = "RA-PSI-GATE-BASELINE-V1"

# Percentage points. Two identical six-repeat runs of the same arm differed by
# about eight, so this default is knowingly finer than six repeats can resolve.
# That is deliberate: the gate says so on every run rather than quietly choosing
# a margin large enough to look confident.
DEFAULT_MARGIN_PP = 5.0

TOLERANCE = 1e-9


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sd_from_ci95(low: float, high: float, runs: int) -> float | None:
    """Recover the spread from the interval `handoff_bench` already published.

    `mean_ci` wrote half = t(n-1) * sd / sqrt(n). Inverting it means the baseline
    needs no extra fields from a run that has already been paid for, and the
    number it records is the one the report showed rather than a second estimate
    of it that could disagree.
    """
    if runs < 2:
        return None
    half = (float(high) - float(low)) / 2.0
    if half < 0:
        return None
    return half * math.sqrt(runs) / T_975.get(runs - 1, 1.96)


def detection_floor(sd_baseline: float, runs_baseline: int, sd_current: float, runs_current: int) -> float:
    """The smallest drop two independent runs of these sizes could tell from noise.

    `check_headroom.smallest_passing_mean` does the matching arithmetic for a
    *paired* design, where both arms ran inside one batch and share its
    conditions. A gate has no pairing available: the baseline was measured weeks
    ago on a different machine on a different day, so the two means are
    independent and their variances add. That is why this is a separate function
    and why its floor is the larger of the two — roughly sqrt(2) times the
    paired one at equal repeats.

    The degrees of freedom use the smaller run rather than a Welch
    approximation. It is the conservative choice, it costs a fraction of a point
    at these repeat counts, and a gate should err towards admitting it cannot
    see something.
    """
    n = min(int(runs_baseline), int(runs_current))
    if n < 2:
        return float("inf")
    standard_error = math.sqrt(float(sd_baseline) ** 2 / runs_baseline + float(sd_current) ** 2 / runs_current)
    return T_975.get(n - 1, 1.96) * standard_error


def repeats_to_detect(margin_pp: float, sd_pp: float, cap: int = 500) -> int | None:
    """How many repeats per run a drop of `margin_pp` would need to be visible.

    Assumes the next run behaves like the recorded one: same spread, same repeat
    count on both sides. Above 30 degrees of freedom the t-table this project
    carries runs out and 1.96 is used, so a number in the hundreds is a lower
    bound on the repeats needed, not a promise.
    """
    if margin_pp <= 0:
        return None
    if sd_pp <= 0:
        return 2
    for n in range(2, cap + 1):
        if T_975.get(n - 1, 1.96) * sd_pp * math.sqrt(2.0 / n) <= margin_pp:
            return n
    return None


def calls_per_run(meta: dict, repeats: int) -> int:
    """Model calls one arm of one benchmark run costs, for one gate invocation.

    Writer calls are one per hop of the chain; reader calls are one per depth
    measured. Stated as calls rather than dollars because the price depends on
    the models a customer chooses, and a made-up dollar figure would be the kind
    of number this project exists to refuse.
    """
    read_at = meta.get("read_at") or [1]
    return int(repeats) * (max(int(hop) for hop in read_at) + len(read_at))


def material(report_path: Path, meta: dict, document: Path | None, quiz: Path | None) -> dict:
    """What the run was measured on, as far as it can be established from disk.

    A baseline that does not name its material is a trap: a drop measured
    against a baseline from a different document is not a regression, it is a
    category error, and it is worse than having no baseline because it looks
    like a result. Every field that could not be established is recorded as
    null, so a thin fingerprint declares its own thinness instead of passing for
    a complete one.
    """
    key = report_path.parent / "answer-key.json"
    return {"document": meta.get("document"),
            "fact_questions": meta.get("fact_questions"),
            "absent_questions": meta.get("absent_questions"),
            "document_sha256": sha256_file(document) if document and document.is_file() else None,
            "quiz_sha256": sha256_file(quiz) if quiz and quiz.is_file() else None,
            "answer_key_sha256": sha256_file(key) if key.is_file() else None}


def material_problems(recorded: dict, current: dict) -> list[str]:
    """Every fingerprint field the baseline recorded that the fresh run cannot match.

    A field the baseline left null is not checked — it never claimed to pin that
    down. A field the baseline recorded and the fresh run cannot produce is a
    problem, not a pass: silence about the material is exactly how a baseline
    from another document gets compared to this one.
    """
    problems = []
    labels = {"document": "document name", "fact_questions": "fact question count",
              "absent_questions": "absent-fact question count", "document_sha256": "document SHA-256",
              "quiz_sha256": "quiz SHA-256", "answer_key_sha256": "answer key SHA-256"}
    for name, label in labels.items():
        was = recorded.get(name)
        if was is None:
            continue
        now_value = current.get(name)
        if now_value is None:
            problems.append("%s was recorded in the baseline but cannot be established for this run" % label)
        elif now_value != was:
            problems.append("%s differs: baseline %r, this run %r" % (label, was, now_value))
    return problems


def usability_of(report: dict, hop: str) -> dict:
    """The benchmark's own usability verdict, reconstructed if it is not stored.

    Reports written before `handoff_bench.usability` existed carry no verdict,
    and the stored MEM-008 runs are among them. Rather than inventing a second
    rule here, the per-arm run and failure counts in the report are turned back
    into the records `usability` expects and the one rule is called. There is
    exactly one definition of an unusable run in this project and this is not it.
    """
    stored = (report.get("meta") or {}).get("usability")
    if stored:
        return stored
    meta = report.get("meta") or {}
    table = (report.get("by_hop") or {}).get(hop) or {}
    failures = meta.get("failures") or []
    arms = sorted(set(table) | {row.get("strategy") for row in failures if row.get("strategy")})
    records: list[dict] = []
    for arm in arms:
        for _ in range(int((table.get(arm) or {}).get("runs", 0))):
            records.append({"strategy": arm, "grades": {hop: {}}})
        for row in failures:
            if row.get("strategy") == arm:
                records.append({"strategy": arm})
    verdict = hb.usability(records, arms)
    verdict["reconstructed"] = True
    return verdict


def invention_rate(row: dict) -> float:
    """Inventions as a share of the absent-fact questions actually put.

    Counts alone would move with the repeat count: twelve repeats invent twice
    as often as six at the same rate. The share is what a change to a prompt
    actually moves.
    """
    asked = float(row.get("absent_questions_asked") or 0)
    if asked <= 0:
        return 0.0
    return float(row.get("inventions", 0)) / asked


def pick_hop(report: dict, hop: str | None) -> str | None:
    hops = report.get("by_hop") or {}
    if hop is not None:
        return hop if hop in hops else None
    if not hops:
        return None
    return max(hops, key=int)


def build_baseline(report: dict, report_path: Path, arm: str, hop: str, margin_pp: float,
                   document: Path | None, quiz: Path | None, replicate: dict | None) -> dict:
    """Record one arm of one run as the thing future runs are measured against."""
    meta = report.get("meta") or {}
    row = ((report.get("by_hop") or {}).get(hop) or {}).get(arm)
    if row is None:
        raise SystemExit("no arm %r at hop %s in %s" % (arm, hop, report_path))
    runs = int(row.get("runs", 0))
    low, high = row.get("ci95") or (row.get("facts_kept_pct"), row.get("facts_kept_pct"))
    sd = sd_from_ci95(low, high, runs)
    baseline = {
        "record_version": RECORD_VERSION,
        "written_at_utc": now(),
        "recorded_from": str(report_path),
        "arm": arm,
        "hop": hop,
        "margin_pp": float(margin_pp),
        "material": material(report_path, meta, document, quiz),
        "measured": {
            "facts_kept_pct": row.get("facts_kept_pct"),
            "ci95": row.get("ci95"),
            "repeats": runs,
            "sd_pp": None if sd is None else round(sd, 3),
            "sd_source": "derived from the 95% interval and repeat count the benchmark published",
            "inventions": row.get("inventions", 0),
            "absent_questions_asked": row.get("absent_questions_asked", 0),
            "invention_rate": round(invention_rate(row), 6),
        },
        "models": {"generator": meta.get("generator"), "reader": meta.get("reader")},
        "read_at": meta.get("read_at"),
        "word_limit": meta.get("word_limit"),
        "usability": usability_of(report, hop),
    }
    if replicate is not None:
        # An interval is a model of the spread. Two runs of the same thing are
        # the spread. When a second identical run is offered, its distance from
        # the first is recorded and the floor never drops below it, because this
        # project has already been caught believing an interval narrower than
        # its own replicates.
        other = ((replicate.get("by_hop") or {}).get(hop) or {}).get(arm)
        if other is None:
            raise SystemExit("the replicate report has no arm %r at hop %s" % (arm, hop))
        gap = abs(float(row.get("facts_kept_pct", 0.0)) - float(other.get("facts_kept_pct", 0.0)))
        baseline["measured"]["observed_replicate_gap_pp"] = round(gap, 3)
        baseline["measured"]["replicate_facts_kept_pct"] = other.get("facts_kept_pct")
    return baseline


def compare(baseline: dict, report: dict, report_path: Path, margin_pp: float | None,
            document: Path | None, quiz: Path | None) -> dict:
    """The whole verdict, as data. `render` turns it into something CI can read."""
    meta = report.get("meta") or {}
    arm = baseline.get("arm")
    hop = baseline.get("hop")
    margin = float(margin_pp if margin_pp is not None else baseline.get("margin_pp", DEFAULT_MARGIN_PP))
    recorded = baseline.get("measured") or {}
    result: dict = {"arm": arm, "hop": hop, "margin_pp": margin, "document": meta.get("document"),
                    "reason_codes": [], "notes": []}

    if baseline.get("record_version") != RECORD_VERSION:
        return {**result, "status": "CANNOT_TELL", "exit_code": 2,
                "reason_codes": ["BASELINE_UNREADABLE"],
                "notes": ["the baseline declares record_version %r, not %r"
                          % (baseline.get("record_version"), RECORD_VERSION)]}

    row = ((report.get("by_hop") or {}).get(hop) or {}).get(arm)
    if row is None:
        return {**result, "status": "CANNOT_TELL", "exit_code": 2, "reason_codes": ["ARM_MISSING"],
                "notes": ["this run has no arm %r at hop %s, which is what the baseline recorded; "
                          "nothing was compared" % (arm, hop)]}

    problems = material_problems(baseline.get("material") or {}, material(report_path, meta, document, quiz))
    if problems:
        # Before anything is compared. A drop measured across two documents is
        # not a smaller finding than a regression, it is a different kind of
        # statement, and reporting it at all would be the error.
        return {**result, "status": "CANNOT_TELL", "exit_code": 2, "reason_codes": ["MATERIAL_MISMATCH"],
                "notes": problems + ["the baseline was not measured on the material this run measured, "
                                     "so no comparison was attempted"]}

    verdict = usability_of(report, hop)
    result["usability"] = verdict

    runs = int(row.get("runs", 0))
    low, high = row.get("ci95") or (row.get("facts_kept_pct"), row.get("facts_kept_pct"))
    sd_now = sd_from_ci95(low, high, runs)
    sd_was = recorded.get("sd_pp")
    result["current"] = {"facts_kept_pct": row.get("facts_kept_pct"), "ci95": row.get("ci95"),
                         "repeats": runs, "sd_pp": None if sd_now is None else round(sd_now, 3),
                         "inventions": row.get("inventions", 0),
                         "absent_questions_asked": row.get("absent_questions_asked", 0),
                         "invention_rate": round(invention_rate(row), 6)}
    result["baseline"] = {k: recorded.get(k) for k in
                          ("facts_kept_pct", "ci95", "repeats", "sd_pp", "inventions",
                           "absent_questions_asked", "invention_rate", "observed_replicate_gap_pp")}

    drop = float(recorded.get("facts_kept_pct", 0.0)) - float(row.get("facts_kept_pct", 0.0))
    result["facts_kept_drop_pp"] = round(drop, 3)
    rate_rise = invention_rate(row) - float(recorded.get("invention_rate", 0.0))
    result["invention_rate_rise"] = round(rate_rise, 6)

    if sd_was is None or sd_now is None:
        floor = float("inf")
    else:
        floor = detection_floor(float(sd_was), int(recorded.get("repeats", 0)), float(sd_now), runs)
        gap = recorded.get("observed_replicate_gap_pp")
        if gap is not None and float(gap) > floor:
            # The receipt beats the model. Two identical runs that actually
            # differed by more than the interval said they could are evidence
            # about this measurement, not an anomaly to be averaged away.
            floor = float(gap)
            result["notes"].append("the floor comes from two identical runs that differed by %.1f points, "
                                   "which is wider than their intervals predicted" % float(gap))
        if float(sd_was) <= 0 and float(sd_now) <= 0:
            result["reason_codes"].append("ZERO_SPREAD_RECORDED")
            result["notes"].append("both runs report zero spread across their repeats, which is unlikely "
                                   "enough to be worth checking; the declared margin is doing all the work")

    smallest = max(margin, floor)
    result["detection_floor_pp"] = None if floor == float("inf") else round(floor, 2)
    result["smallest_detectable_drop_pp"] = None if smallest == float("inf") else round(smallest, 2)
    needed = None
    if sd_now is not None and floor != float("inf") and floor > margin:
        needed = repeats_to_detect(margin, max(float(sd_was or 0.0), float(sd_now)))
        result["reason_codes"].append("MARGIN_BELOW_DETECTION_FLOOR")
        result["repeats_needed_for_margin"] = needed
        result["calls_needed_for_margin"] = None if needed is None else calls_per_run(meta, needed)
        result["calls_per_run_now"] = calls_per_run(meta, runs)

    # Order matters. An unusable run is reported as unusable even if its numbers
    # also happen to have fallen: a run that may not be analysed cannot supply a
    # finding, and dressing one up as a regression would be the same mistake in
    # the other direction.
    if not verdict.get("usable", True):
        result["status"] = "CANNOT_TELL"
        result["exit_code"] = 2
        result["reason_codes"].append("RUN_UNUSABLE")
        result["notes"].append(verdict.get("reason") or "the run is unusable")
        result["notes"].append("this fails the build, and it is not a finding: nothing was measured, "
                               "and an unmeasured run is not a run without a regression")
        return result

    if rate_rise > TOLERANCE:
        # No noise floor here, and the asymmetry is deliberate. A drop of a few
        # points in retention is the same kind of event as run-to-run variation;
        # a handover that states something the document never said is a
        # different kind of event, and the arms in this project invent nothing
        # at all. One is worth a build failure.
        result["status"] = "REGRESSION"
        result["exit_code"] = 1
        result["reason_codes"].append("INVENTIONS_ROSE")
        result["notes"].append("the handover answered %d of %d questions the document never answers, "
                               "against %d of %d at the baseline"
                               % (row.get("inventions", 0), row.get("absent_questions_asked", 0),
                                  recorded.get("inventions", 0), recorded.get("absent_questions_asked", 0)))
        return result

    if floor == float("inf"):
        # Checked after inventions and before retention, because the two are not
        # alike. An invented fact is visible in a single run; a few points of
        # retention are not visible in any number of runs whose spread was never
        # measured. Passing here would be claiming a comparison that was never
        # possible.
        result["status"] = "CANNOT_TELL"
        result["exit_code"] = 2
        result["reason_codes"].append("NO_SPREAD_RECORDED")
        result["notes"].append("one of the two runs has fewer than two repeats, so it has no measurable "
                               "spread; a single run cannot be told apart from run-to-run variation at "
                               "any drop, and this one is not being reported either way")
        return result

    if drop > smallest + TOLERANCE:
        result["status"] = "REGRESSION"
        result["exit_code"] = 1
        result["reason_codes"].append("FACTS_KEPT_DROPPED")
        return result

    result["status"] = "PASS"
    result["exit_code"] = 0
    if drop > margin + TOLERANCE:
        result["reason_codes"].append("DROP_WITHIN_NOISE")
    return result


def render(result: dict) -> str:
    """A CI log is read by a person in a hurry. Five lines, then the reasoning."""
    lines = ["RA-PSI memory gate: %s" % result["status"]]
    where = "arm `%s`, after %s handover(s)" % (result.get("arm"), result.get("hop"))
    if result.get("document"):
        where += ", document `%s`" % result["document"]
    lines.append(where.capitalize() + ".")
    lines.append("")

    if result["status"] == "CANNOT_TELL":
        # No numbers. `handoff_bench.render_report` and `diagnose_report` both
        # refuse to print a table for a run that may not be analysed, and a
        # percentage printed above a refusal is the thing people quote.
        lines.append("Verdict: this gate could not tell whether there was a regression, so it fails the "
                     "build without reporting one. No numbers are shown, because none of them are a result.")
        for note in result.get("notes", []):
            lines.append("  - " + note)
        lines += ["", "Exit %d (0 pass, 1 regression, 2 cannot tell)." % result["exit_code"]]
        return "\n".join(lines) + "\n"

    base, cur = result.get("baseline") or {}, result.get("current") or {}
    if cur:
        moved = result.get("facts_kept_drop_pp", 0.0)
        change = ("unchanged" if abs(moved) <= TOLERANCE
                  else ("down %.1f points" % moved if moved > 0 else "up %.1f points" % -moved))
        lines.append("Facts kept:  %.1f%% at baseline (%s repeats) -> %.1f%% now (%s repeats), %s."
                     % (base.get("facts_kept_pct", 0.0), base.get("repeats"),
                        cur.get("facts_kept_pct", 0.0), cur.get("repeats"), change))
        lines.append("Invented:    %d of %d at baseline -> %d of %d now."
                     % (base.get("inventions", 0), base.get("absent_questions_asked", 0),
                        cur.get("inventions", 0), cur.get("absent_questions_asked", 0)))
    lines.append("Margin:      %.1f points, declared." % result.get("margin_pp", 0.0))
    smallest = result.get("smallest_detectable_drop_pp")
    lines.append("Sensitivity: the smallest drop this comparison could have detected is %s."
                 % ("%.1f points" % smallest if smallest is not None else "not computable"))
    lines.append("")

    if result["status"] == "REGRESSION":
        if "INVENTIONS_ROSE" in result["reason_codes"]:
            lines.append("Verdict: the handover invented facts it did not invent at the baseline. "
                         "Inventions are not noise-gated: this arm invented nothing before.")
        else:
            lines.append("Verdict: fact retention fell by %.1f points, past both the declared %.1f-point "
                         "margin and the %.1f-point noise floor of these two runs. This is a regression."
                         % (result.get("facts_kept_drop_pp", 0.0), result.get("margin_pp", 0.0),
                            result.get("detection_floor_pp") or 0.0))
    else:
        if "DROP_WITHIN_NOISE" in result["reason_codes"]:
            lines.append("Verdict: fact retention fell by %.1f points, which is inside the %.1f-point "
                         "run-to-run noise of these two runs. That is not distinguishable from measuring "
                         "the same system twice, so it is not reported as a regression."
                         % (result.get("facts_kept_drop_pp", 0.0), result.get("detection_floor_pp") or 0.0))
        else:
            lines.append("Verdict: no regression. Retention is within the declared margin and nothing new "
                         "was invented.")

    for note in result.get("notes", []):
        lines.append("  - " + note)

    # Only on a pass. A gate that fired has already proved it can see something;
    # a gate that passed is the one whose blindness the reader needs told.
    if result["status"] == "PASS" and "MARGIN_BELOW_DETECTION_FLOOR" in result.get("reason_codes", []):
        needed = result.get("repeats_needed_for_margin")
        lines += ["",
                  "Blind spot: your %.1f-point margin is below this comparison's %.1f-point detection "
                  "floor. A real regression between those two numbers passes this gate unseen."
                  % (result.get("margin_pp", 0.0), result.get("detection_floor_pp") or 0.0)]
        if needed:
            # Plain ASCII from here down: this text is read in a CI log, and
            # not every runner's console agrees with this file's encoding.
            lines.append("  To see %.1f points you would need about %d repeats per run: roughly %s model "
                         "calls per gate run, against %s now."
                         % (result.get("margin_pp", 0.0), needed, result.get("calls_needed_for_margin"),
                            result.get("calls_per_run_now")))
        else:
            lines.append("  No repeat count under 500 reaches that margin at this spread. The honest move "
                         "is to raise the margin, not the budget.")
    lines.append("")
    lines.append("Exit %d (0 pass, 1 regression, 2 cannot tell)." % result["exit_code"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", type=Path, required=True,
                        help="a report.json written by handoff_bench, or the folder holding one")
    parser.add_argument("--baseline", type=Path, help="the recorded baseline to compare against")
    parser.add_argument("--write-baseline", type=Path,
                        help="record this run as the baseline instead of comparing against one")
    parser.add_argument("--replicate", type=Path,
                        help="with --write-baseline: a second report of the same arm, so the recorded "
                             "noise floor is an observed one rather than a modelled one")
    parser.add_argument("--arm", default=hb.CONTROL,
                        help="the strategy whose retention is gated; with --baseline the baseline decides")
    parser.add_argument("--hop", help="chain depth to gate, defaulting to the deepest the report measured; "
                                      "with --baseline the baseline decides")
    parser.add_argument("--margin", type=float,
                        help="the drop in percentage points that counts as a regression, if it also "
                             "clears the noise floor (default %.1f)" % DEFAULT_MARGIN_PP)
    parser.add_argument("--document", type=Path, help="the measured document, to fingerprint the material")
    parser.add_argument("--quiz", type=Path, help="the quiz, to fingerprint the material")
    parser.add_argument("--json", action="store_true", help="print the verdict as JSON instead of prose")
    args = parser.parse_args()

    report_path = args.report / "report.json" if args.report.is_dir() else args.report
    if not report_path.is_file():
        raise SystemExit("no report at %s" % report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))

    if args.write_baseline:
        hop = pick_hop(report, args.hop)
        if hop is None:
            raise SystemExit("no hop %s in %s" % (args.hop, report_path))
        replicate = None
        if args.replicate:
            path = args.replicate / "report.json" if args.replicate.is_dir() else args.replicate
            replicate = json.loads(path.read_text(encoding="utf-8"))
        baseline = build_baseline(report, report_path, args.arm, hop,
                                  args.margin if args.margin is not None else DEFAULT_MARGIN_PP,
                                  args.document, args.quiz, replicate)
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(json.dumps(baseline, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
        print(json.dumps({"wrote": str(args.write_baseline), "arm": args.arm, "hop": hop,
                          "repeats": baseline["measured"]["repeats"],
                          "sd_pp": baseline["measured"]["sd_pp"],
                          "material_fields_pinned": sorted(k for k, v in baseline["material"].items()
                                                           if v is not None)},
                         indent=2, ensure_ascii=False))
        return

    if not args.baseline:
        raise SystemExit("give --baseline to compare against, or --write-baseline to record one")
    if not args.baseline.is_file():
        raise SystemExit("no baseline at %s" % args.baseline)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    result = compare(baseline, report, report_path, args.margin, args.document, args.quiz)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else render(result), end="")
    if result["exit_code"]:
        raise SystemExit(result["exit_code"])


if __name__ == "__main__":
    main()
