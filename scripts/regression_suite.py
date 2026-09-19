#!/usr/bin/env python3
"""Recompute every published verdict from the stored answers, calling no model.

The project makes one promise more often than any other, in its posts, its
result files and its public page: *every published verdict can be recomputed
from the stored answers, without calling a model*. Until now that promise was
kept for two experiments. `tests/test_published_results.py` regrades MEM-004 and
MEM-005 and stops there; everything else was published on trust.

This walks every experiment that carries a verdict, recomputes it from the raw
answers on disk, and says whether the recomputation agrees with what was
published. It calls nothing, over the network or otherwise: grading is the
comparison of letters to a key that was frozen before the run, and every
aggregate is a pure function of those letters.

Four result shapes exist, and the suite refuses to pretend they are one:

* **adjudicated** (MEM-001, MEM-002) — a verdict produced by
  `adjudicate_evaluations.adjudicate` from a stored evaluation packet. The
  evaluators were models, but the adjudication is arithmetic over their filed
  scorecards, so the verdict is recomputable even though the scores were not.
* **paired quiz** (MEM-004 to MEM-007) — per-trial reader answers, paired by
  `pair_id`, decided by `handoff_quiz.decide` against a pre-registered rule.
* **chain** (MEM-008, MEM-010 to MEM-012) — one record per chain, `grades`
  keyed by hop, aggregated per document by `handoff_bench.summarise`. There is
  no `decision.json`: the published numbers are the tables in each document's
  `report.json`, which is what RESULT.md and the registry quote.
* **anything else** — reported as *unverifiable*, never skipped.

That last category is the reason this exists. An experiment whose stored data
cannot reproduce its own published number is a finding, and a suite that
silently passed over it would leave the project claiming more than it can show.
So *unverifiable* is a distinct outcome from *mismatched*, and both are loud.

The suite reads. It never writes into `experiments/`. If a published number
turns out not to be reproducible, the answer is to say so, not to move the
number.

Sealed material is deliberately out of scope: only `PROP-EXP-*` is walked, so
`HOLDOUT-2026-09` and the live panel are never opened.

  python scripts/regression_suite.py
  python scripts/regression_suite.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import adjudicate_evaluations as ae  # noqa: E402
import handoff_bench as hb  # noqa: E402
import handoff_quiz as hq  # noqa: E402

# Absolute tolerance for every numeric comparison. The published numbers were
# written by the same functions this suite calls, so agreement should be exact;
# the tolerance exists to absorb the last bit of a double, not to hide drift.
# It is reported next to the results so nobody has to guess what "agree" meant.
TOLERANCE = 1e-9

REPRODUCED = "reproduced"
MISMATCH = "mismatch"
UNVERIFIABLE = "unverifiable"
NO_VERDICT = "no_verdict"

# Exit codes. A mismatch outranks an unverifiable: if both occur, the caller is
# told about the mismatch, because a wrong published number is worse than an
# unbacked one.
EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_UNVERIFIABLE = 2

SKIP_RESULT_FILES = frozenset({"answer-key.json", "report.json", "decision.json",
                               "experiment-manifest.json", "run-report.json"})


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def repository_of(experiment: Path) -> Path:
    """The checkout an experiment directory belongs to, so a fixture stays a fixture.

    Every path in this module is resolved against the repository the experiment
    came from rather than against the one this file happens to live in. A test
    that builds a synthetic experiment in a temporary directory must not have it
    silently measured against the real results.
    """
    return experiment.parents[1]


def shown(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def differences(recomputed, published, field: str = "") -> list[dict]:
    """Every leaf on which the two disagree, named by its path.

    Structures are walked rather than rendered and compared as text: two floats
    that print the same can differ, and two that differ in the last bit are not
    a finding. Numbers are compared with TOLERANCE, everything else exactly.
    """
    if isinstance(recomputed, dict) and isinstance(published, dict):
        found = []
        for name in sorted(set(recomputed) | set(published)):
            path = name if not field else "%s.%s" % (field, name)
            if name not in recomputed:
                found.append({"field": path, "recomputed": None, "published": published[name],
                              "why": "the recomputation does not produce this field"})
            elif name not in published:
                found.append({"field": path, "recomputed": recomputed[name], "published": None,
                              "why": "the published file does not contain this field"})
            else:
                found.extend(differences(recomputed[name], published[name], path))
        return found
    if isinstance(recomputed, list) and isinstance(published, list):
        if len(recomputed) != len(published):
            return [{"field": field or "(root)", "recomputed": len(recomputed), "published": len(published),
                     "why": "different number of entries"}]
        found = []
        for index, (mine, theirs) in enumerate(zip(recomputed, published)):
            found.extend(differences(mine, theirs, "%s[%d]" % (field or "(root)", index)))
        return found
    numeric = (int, float)
    if isinstance(recomputed, numeric) and isinstance(published, numeric) \
            and not isinstance(recomputed, bool) and not isinstance(published, bool):
        gap = abs(float(recomputed) - float(published))
        if gap <= TOLERANCE:
            return []
        return [{"field": field or "(root)", "recomputed": recomputed, "published": published,
                 "why": "differs by %.6g, above the tolerance of %g" % (gap, TOLERANCE)}]
    if recomputed == published:
        return []
    return [{"field": field or "(root)", "recomputed": recomputed, "published": published,
             "why": "values differ"}]


def unit(name: str, kind: str, status: str, **rest) -> dict:
    """One thing that was checked: a decision file, or one document of a chain."""
    row = {"unit": name, "kind": kind, "status": status, "checks": 0, "differences": [], "notes": []}
    row.update(rest)
    return row


# --- adjudicated verdicts (MEM-001, MEM-002) ---------------------------------


def check_adjudicated(experiment: Path) -> list[dict]:
    """Re-run the adjudication over the filed scorecards and compare the verdict.

    The scores came from judge models and cannot be recomputed. The *decision*
    can: it is a tally over cards that are stored, and the packet's hash is part
    of the published decision, so a card edited afterwards moves `input_sha256`
    and is caught here rather than argued about.
    """
    packet_path = experiment / "results" / "scorecards" / "evaluation-packet.json"
    published_path = experiment / "results" / "decision.json"
    root = repository_of(experiment)
    row = unit("decision.json", "adjudicated", REPRODUCED, source=shown(packet_path, root))
    if not packet_path.is_file():
        row["status"] = UNVERIFIABLE
        row["notes"].append("no evaluation packet is stored, so the adjudication cannot be re-run")
        return [row]
    published = load(published_path)
    again = ae.adjudicate(load(packet_path))
    compared = {field: again.get(field) for field in ("decision", "status", "reason_codes", "input_sha256")}
    against = {field: published.get(field) for field in ("decision", "status", "reason_codes", "input_sha256")}
    row["checks"] = len(compared)
    row["differences"] = differences(compared, against)
    row["effect"] = {"recomputed": compared, "published": against}
    if row["differences"]:
        row["status"] = MISMATCH
    return [row]


# --- paired quiz verdicts (MEM-004 to MEM-007) -------------------------------


def answers_directory(experiment: Path, decision_path: Path, published: dict | None = None) -> Path | None:
    """Where the reader answers behind one decision file live.

    A run may publish more than one decision — MEM-006 published a second
    reading by a different reader. The convention is a sibling directory named
    after it. Guessing wrong would regrade one reader's decision from another
    reader's answers and call the disagreement a mismatch, so a decision whose
    answers cannot be located is reported as unverifiable instead.

    A reading the protocol *set aside* breaks that convention, and looking only
    at the decision's own name is what made this suite report MEM-006's second
    reading as resting on nothing. It does not: MEM-006's deviation D3 moved the
    whole Kimi reading to `results/quiz/abandoned/reader-nvidia-kimi-k3/` and
    published its verdict as `decision-kimi-reader.json`. The folder is named
    after the reader and the file after a slug, so the two never meet by name.
    The decision's own `reader` field is the link, and it is the only one that
    cannot pick up a different reader's answers by accident.
    """
    results = experiment / "results"
    if decision_path.parent != results:
        return decision_path.parent
    if decision_path.name == "decision.json":
        return results / "quiz"
    slug = decision_path.stem[len("decision-"):]
    candidates = [results / ("quiz-%s" % slug), results / slug]
    reader = (published or {}).get("reader")
    if reader:
        candidates.append(results / "quiz" / "abandoned" / str(reader))
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def wrong_reader(directory: Path, record: dict) -> bool:
    """Whether a record filed under an abandoned reader was written by another one.

    Only the abandoned folders are checked, because only there is the folder's
    name an `evaluator_id` that a record repeats. Elsewhere the two are written
    in different vocabularies — a cross-read folder is named `cross-read-deepseek`
    and holds records whose reader_id is `cross-deepseek` — and comparing them
    would reject good evidence.
    """
    return directory.parent.name == "abandoned" and \
        record.get("reader_id") not in (None, directory.name)


def quiz_and_key(experiment: Path) -> tuple[list[dict], dict[str, str]]:
    """The rendered quiz and its letter key, rebuilt from the pre-registered file."""
    policy = load(experiment / "evaluation_policy.json")
    quiz = load(experiment / policy["quiz"]["file"])
    return hq.render_quiz(quiz, experiment.name + ":" + quiz["quiz_version"])


def check_paired_quiz(experiment: Path) -> list[dict]:
    rows = []
    root = repository_of(experiment)
    results = experiment / "results"
    decisions = sorted(path for path in results.glob("decision*.json")) \
        + sorted(path for path in results.glob("*/decision.json"))
    policy_path = experiment / "evaluation_policy.json"
    for decision_path in decisions:
        name = str(decision_path.relative_to(results)).replace("\\", "/")
        row = unit(name, "paired quiz", REPRODUCED)
        published = load(decision_path)
        directory = answers_directory(experiment, decision_path, published)
        if directory is None or not directory.is_dir():
            row["status"] = UNVERIFIABLE
            row["notes"].append("no directory of reader answers accompanies this decision, so its "
                                "numbers rest on nothing that can be regraded")
            row["effect"] = {"recomputed": None, "published": summary_effect(published)}
            rows.append(row)
            continue
        row["source"] = shown(directory, root)
        if not policy_path.is_file():
            row["status"] = UNVERIFIABLE
            row["notes"].append("no evaluation_policy.json, so the quiz and the rule are unknown")
            rows.append(row)
            continue
        policy = load(policy_path)
        rendered, key = quiz_and_key(experiment)
        checks = 0
        found: list[dict] = []
        stored_key_path = directory / "answer-key.json"
        if stored_key_path.is_file():
            checks += 1
            found.extend(differences(key, load(stored_key_path)["key"], "answer_key"))
        else:
            row["notes"].append("no answer-key.json beside these answers; the key was rebuilt from %s"
                                % policy["quiz"]["file"])
        pairs: dict[str, dict] = {}
        graded = 0
        foreign = ""
        for path in sorted(directory.glob("*.json")):
            if path.name in SKIP_RESULT_FILES:
                continue
            record = load(path)
            if "answers" not in record or "condition" not in record:
                continue
            if wrong_reader(directory, record):
                foreign = "%s was written by %r, not by the reader this decision names; refusing to " \
                          "regrade one reader's verdict from another's answers" \
                          % (path.name, record.get("reader_id"))
                break
            again = hq.grade(record["answers"], key, rendered)
            if "grade" in record:
                checks += 1
                found.extend(differences(again, record["grade"], "%s.grade" % path.name))
            graded += 1
            pairs.setdefault(record["pair_id"], {"pair_id": record["pair_id"]})[record["condition"]] = again
        if foreign or not graded:
            row["status"] = UNVERIFIABLE
            row["notes"].append(foreign or "the directory holds no record carrying raw answers")
            row["effect"] = {"recomputed": None, "published": summary_effect(published)}
            rows.append(row)
            continue
        complete = sorted((pair for pair in pairs.values() if "baseline" in pair and "structured" in pair),
                          key=lambda pair: pair["pair_id"])
        # The rule is read from the pre-registered policy, not from the decision
        # file: a decision that quietly carried a different threshold from the
        # one registered would otherwise reproduce itself. A decision that filed
        # no rule at all is a gap in the record, not a number that moved.
        if published.get("rule"):
            checks += 1
            found.extend(differences({k: policy["quiz"][k] for k in ("keep_min_delta_pp", "invention_margin")},
                                     published["rule"], "rule"))
        else:
            row["notes"].append("this decision records no rule of its own; it was regraded under the rule "
                                "in evaluation_policy.json")
        again = hq.decide(complete, policy["quiz"])
        compared = {"decision": again["decision"], "reason_codes": again["reason_codes"],
                    "summary": again["summary"]}
        against = {"decision": published.get("decision"), "reason_codes": published.get("reason_codes"),
                   "summary": published.get("summary", {})}
        checks += 2 + len(again["summary"])
        found.extend(differences(compared, against))
        row["checks"] = checks
        row["differences"] = found
        row["records"] = graded
        row["effect"] = {"recomputed": summary_effect(again), "published": summary_effect(published)}
        if found:
            row["status"] = MISMATCH
        rows.append(row)
    return rows


def summary_effect(decision: dict) -> dict:
    """The headline of a paired verdict, in the terms the project publishes it."""
    summary = decision.get("summary") or {}
    return {"decision": decision.get("decision"), "pairs": summary.get("pairs"),
            "mean_paired_delta_pp": summary.get("mean_paired_delta_pp"),
            "ci95_delta_pp": summary.get("ci95_delta_pp"),
            "inventions": summary.get("inventions")}


# --- chain verdicts (MEM-008, MEM-010 to MEM-012) ----------------------------


def control_arm(table: dict) -> str | None:
    """The arm everything else is compared against: the one with no comparison.

    Read from the published table rather than hard-coded, because the two chain
    harnesses disagree — `handoff_bench` controls on `summary`, `anchored_chain`
    on `bare` — and a wrong guess would recompute a different experiment.
    """
    for hop in sorted(table, key=int):
        bare = [name for name, row in table[hop].items() if "vs_control_pp" not in row]
        if len(bare) == 1:
            return bare[0]
    return None


def rederive_chain_key(root: Path, document: str, stored: dict[str, str]) -> str | None:
    """The quiz file that produces this stored key, if the repository still has it.

    MEM-008 keeps its quizzes; the later chain experiments reused documents that
    are not filed under them, so their key can only be taken as stored. Finding
    the quiz closes the loop back to a pre-registered artefact, and not finding
    it is a note, not a failure: the key is still frozen next to the answers.
    """
    for path in sorted((root / "experiments").glob("PROP-EXP-*/quiz-%s.json" % document)):
        quiz = load(path)
        _rendered, key = hq.render_quiz(quiz, "%s.md:%s" % (document, quiz["quiz_version"]))
        if key == stored:
            return shown(path, root)
    return None


def chain_records(directory: Path, key: dict[str, str], rendered: list[dict]) -> tuple[list[dict], list[dict], int]:
    """Regrade every chain record in a document's directory, in run order.

    Order matters: `summarise` pairs an arm against the control by position, so
    records are sorted the way the harness generated them — by arm, then by
    repeat. Failed runs are left out, exactly as `summarise` leaves them out.
    """
    records, found, checks = [], [], 0
    for path in sorted(directory.glob("*.json")):
        if path.name in SKIP_RESULT_FILES or path.name.endswith(".failed.json"):
            continue
        record = load(path)
        if "grades" not in record or "strategy" not in record:
            continue
        grades = {}
        for hop, stored in record["grades"].items():
            again = hq.grade(stored.get("answers", {}), key, rendered)
            checks += 1
            found.extend(differences(again, {name: stored[name] for name in again if name in stored},
                                     "%s.grades.%s" % (path.name, hop)))
            grades[hop] = {**stored, **again}
        records.append({**record, "grades": grades})
    records.sort(key=lambda record: (record["strategy"], record.get("repeat", 0)))
    return records, found, checks


def retrieval_block(records: list[dict], arm: str | None) -> dict:
    """What one arm looked up, and how often it aimed at something the note had lost."""
    counts: dict[str, int] = {}
    total = on_gap = 0
    for record in records:
        if arm is not None and record.get("strategy") != arm:
            continue
        for step in record.get("chain", []):
            for entry_id in step.get("retrieved", []):
                counts[entry_id] = counts.get(entry_id, 0) + 1
                total += 1
            on_gap += len(step.get("on_a_gap") or ())
    if not total:
        return {}
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return {"retrievals": total, "distinct_entries": len(counts), "on_a_gap": on_gap,
            "gap_targeting_pct": round(100.0 * on_gap / total, 1),
            "most_retrieved": [{"id": entry_id, "times": times} for entry_id, times in ranked[:10]]}


def recompute_retrieval(records: list[dict], published: dict) -> dict:
    """The retrieval log, in whichever shape the run published, minus the labels.

    MEM-010 and MEM-011 published one flat block covering every arm that
    retrieved; MEM-012 added gap targeting and a block per arm. Recomputing the
    newer shape and comparing it to the older one would report a mismatch where
    there is only a change of format, so the published shape decides.

    Labels are dropped on both sides: `anchored_chain.retrieval_log` copies them
    from the ledger, so they are a property of the archive rather than a number
    derived from the answers, and two of the three ledgers are not filed with
    the experiment that used them.
    """
    if "retrievals" in published:
        return retrieval_block(records, None)
    return {arm: retrieval_block(records, arm) for arm in sorted(published)}


def strip_labels(block: dict) -> dict:
    """Drop the ledger labels, and any field the older report never recorded."""
    if "retrievals" in block:
        return {name: ([{"id": item["id"], "times": item["times"]} for item in value]
                       if name == "most_retrieved" else value)
                for name, value in block.items()}
    return {arm: strip_labels(row) for arm, row in block.items()}


def project(recomputed: dict, published: dict) -> dict:
    """Keep only what was published: an older report cannot be faulted for silence."""
    if "retrievals" in published:
        return {name: value for name, value in recomputed.items() if name in published}
    return {arm: project(recomputed.get(arm, {}), row) for arm, row in published.items()}


def chain_effect(table: dict, control: str | None) -> dict:
    """Each arm against the control at the deepest hop measured, in points."""
    if not table or control is None:
        return {}
    deepest = max(table, key=int)
    return {"hop": int(deepest),
            "vs_%s_pp" % control: {name: row.get("vs_control_pp")
                                   for name, row in sorted(table[deepest].items()) if name != control}}


def check_chain(experiment: Path) -> list[dict]:
    rows = []
    root = repository_of(experiment)
    for directory in sorted(path for path in (experiment / "results").iterdir() if path.is_dir()):
        report_path = directory / "report.json"
        if not report_path.is_file():
            continue
        row = unit(directory.name, "chain", REPRODUCED, source=shown(directory, root))
        published = load(report_path)
        if "by_hop" not in published:
            row["status"] = UNVERIFIABLE
            row["notes"].append("this report has no per-hop table; it is not a chain benchmark and this "
                                "suite has no rule for recomputing it")
            row["effect"] = {"recomputed": None, "published": None}
            rows.append(row)
            continue
        key_path = directory / "answer-key.json"
        if not key_path.is_file():
            row["status"] = UNVERIFIABLE
            row["notes"].append("no answer-key.json, so nothing can be regraded")
            rows.append(row)
            continue
        stored = load(key_path)
        key, rendered = stored["key"], stored["rendered"]
        origin = rederive_chain_key(root, directory.name, key)
        row["notes"].append("answer key re-derived from %s" % origin if origin else
                            "answer key taken as stored; the quiz that produced it is not in this repository")
        records, found, checks = chain_records(directory, key, rendered)
        if not records:
            row["status"] = UNVERIFIABLE
            row["notes"].append("no record in this directory carries raw answers; the published table "
                                "cannot be recomputed, only re-read")
            row["effect"] = {"recomputed": None, "published": None}
            rows.append(row)
            continue
        control = control_arm(published["by_hop"])
        if control is None:
            row["status"] = UNVERIFIABLE
            row["notes"].append("the published table names no control arm, so the paired comparisons "
                                "cannot be reproduced")
            rows.append(row)
            continue
        again = {hop: hb.summarise(records, int(hop), control=control) for hop in published["by_hop"]}
        checks += sum(len(arm) for table in again.values() for arm in table.values())
        found.extend(differences(again, published["by_hop"], "by_hop"))
        meta = published.get("meta", {})
        failed = len(list(directory.glob("*.failed.json")))
        checks += 1
        found.extend(differences(failed, meta.get("failed_runs", 0), "meta.failed_runs"))
        if meta.get("retrieval"):
            wanted = strip_labels(meta["retrieval"])
            mine = project(recompute_retrieval(records, meta["retrieval"]), wanted)
            checks += len(wanted)
            found.extend(differences(mine, wanted, "meta.retrieval"))
            row["notes"].append("retrieval labels are not compared: they are copied from the ledger, "
                                "not derived from the answers")
        row["checks"] = checks
        row["differences"] = found
        row["records"] = len(records)
        row["control"] = control
        row["effect"] = {"recomputed": chain_effect(again, control),
                         "published": chain_effect(published["by_hop"], control)}
        if found:
            row["status"] = MISMATCH
        rows.append(row)
    return rows


# --- walking the registry ----------------------------------------------------


def has_verdict(experiment: Path, entry: dict) -> bool:
    """Whether the project has said anything about this experiment's outcome."""
    if (experiment / "results" / "decision.json").is_file():
        return True
    return entry.get("status", "OPEN") not in ("OPEN", "PROPOSED", "")


def shape_of(experiment: Path) -> str:
    if (experiment / "results" / "scorecards" / "evaluation-packet.json").is_file():
        return "adjudicated"
    if list((experiment / "results").glob("decision*.json")) or \
            list((experiment / "results").glob("*/decision.json")):
        return "paired quiz"
    if list((experiment / "results").glob("*/report.json")):
        return "chain"
    return "unknown"


def run(root: Path = ROOT) -> dict:
    """Every experiment with a verdict, recomputed. Nothing is skipped silently."""
    registry = {entry["experiment_id"]: entry for entry in
                load(root / "experiments" / "registry.json")["experiments"]}
    experiments = []
    for directory in sorted((root / "experiments").glob("PROP-EXP-*")):
        entry = registry.get(directory.name, {})
        row = {"experiment_id": directory.name, "registered_status": entry.get("status", "OPEN"),
               "shape": None, "status": NO_VERDICT, "units": []}
        if not (directory / "results").is_dir() or not has_verdict(directory, entry):
            row["note"] = "no verdict is published for this experiment, so there is nothing to reproduce"
            experiments.append(row)
            continue
        shape = shape_of(directory)
        row["shape"] = shape
        if shape == "adjudicated":
            row["units"] = check_adjudicated(directory)
        elif shape == "paired quiz":
            row["units"] = check_paired_quiz(directory)
        elif shape == "chain":
            row["units"] = check_chain(directory)
        if not row["units"]:
            row["status"] = UNVERIFIABLE
            row["units"] = [unit("(whole experiment)", shape, UNVERIFIABLE,
                                 notes=["a verdict is published but no stored result of a shape this "
                                        "suite knows how to recompute accompanies it"])]
        statuses = {item["status"] for item in row["units"]}
        row["status"] = MISMATCH if MISMATCH in statuses else \
            (UNVERIFIABLE if UNVERIFIABLE in statuses else REPRODUCED)
        row["checks"] = sum(item["checks"] for item in row["units"])
        experiments.append(row)
    counts = {name: sum(1 for row in experiments if row["status"] == name)
              for name in (REPRODUCED, MISMATCH, UNVERIFIABLE, NO_VERDICT)}
    return {"record_version": "RA-PSI-REGRESSION-V1", "tolerance": TOLERANCE,
            "models_called": 0, "experiments": experiments, "counts": counts,
            "checks": sum(row.get("checks", 0) for row in experiments),
            "exit_code": EXIT_MISMATCH if counts[MISMATCH] else
                         (EXIT_UNVERIFIABLE if counts[UNVERIFIABLE] else EXIT_OK)}


def render(report: dict) -> str:
    """One line per unit, and the differences spelled out under the ones that moved."""
    lines = ["RA-PSI regression suite — published verdicts recomputed from stored answers.",
             "No model was called. Numbers agree when they differ by at most %g (absolute)." % report["tolerance"],
             ""]
    for row in report["experiments"]:
        if row["status"] == NO_VERDICT:
            lines.append("%-20s %-13s %s" % (row["experiment_id"], "no verdict", row.get("note", "")))
            continue
        lines.append("%-20s %-13s %s, %d numbers checked"
                     % (row["experiment_id"], row["status"], row["shape"], row.get("checks", 0)))
        for item in row["units"]:
            lines.append("    %-28s %-13s %s" % (item["unit"], item["status"], effect_line(item)))
            for note in item["notes"]:
                lines.append("        note: %s" % note)
            for difference in item["differences"][:20]:
                lines.append("        %s: recomputed %r, published %r — %s"
                             % (difference["field"], difference["recomputed"],
                                difference["published"], difference["why"]))
            if len(item["differences"]) > 20:
                lines.append("        ... and %d more" % (len(item["differences"]) - 20))
    counts = report["counts"]
    lines += ["", "%d reproduced, %d mismatched, %d unverifiable, %d without a verdict; %d numbers checked."
              % (counts[REPRODUCED], counts[MISMATCH], counts[UNVERIFIABLE], counts[NO_VERDICT],
                 report["checks"])]
    if counts[MISMATCH]:
        lines.append("A published number does not follow from the stored answers. Do not edit the stored "
                     "answers; report which number moved.")
    if counts[UNVERIFIABLE]:
        lines.append("Some published numbers rest on data that is not stored. They are not wrong; they are "
                     "not checkable, which is the claim this project makes about them.")
    return "\n".join(lines) + "\n"


def effect_line(item: dict) -> str:
    effect = item.get("effect") or {}
    mine, theirs = effect.get("recomputed"), effect.get("published")
    if mine is None and theirs is None:
        return ""
    if mine == theirs:
        return "effect %s (agrees)" % compact(theirs)
    return "recomputed %s vs published %s" % (compact(mine), compact(theirs))


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository to check")
    parser.add_argument("--json", action="store_true", help="emit the full report instead of the summary")
    args = parser.parse_args(argv)
    report = run(args.root)
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else render(report), end="")
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
