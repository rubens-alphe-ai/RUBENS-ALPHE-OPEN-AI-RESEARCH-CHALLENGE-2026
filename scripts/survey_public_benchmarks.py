#!/usr/bin/env python3
"""Run the item analysis across every public benchmark we can legally reach.

One audit of one benchmark is an anecdote. The question a buyer, a reviewer and
a regulator all ask next is the same: *is my benchmark unusual, or is this
everywhere?* Nobody can answer that today, because nobody has run item
statistics across a field of benchmarks.

This does. It walks HELM's release manifests, finds every question-set answered
by enough models to support item statistics, imports each one through
`import_public_results.py`, and runs `item_analysis.py` over the result. One row
per question-set.

WHAT COUNTS AS A QUESTION-SET. A HELM run name is `scenario:settings,model=X`.
Everything before `,model=` decides which questions were asked; the model is the
respondent. So two runs belong to the same question-set exactly when that prefix
matches, and `math:subject=algebra,level=1` is a different set from `level=5`
even though both are `math`. Getting this wrong would pool questions nobody
answered together, which is the one mistake that would invalidate everything
downstream.

WHAT IT REFUSES. A scenario whose metric is not already 0 or 1 -- translation
scored by BLEU, summarisation scored by ROUGE -- is refused by the importer
rather than thresholded, and lands here as a recorded failure with its reason.
That is the correct outcome, not a gap: where the cut falls would change every
number, and it is not a decision to make inside a survey.

Failures are counted and listed. A survey that reports only what worked is a
survey of what worked.

COST. Nothing here calls a model. It reads files a public bucket already serves,
caches them, and does arithmetic. The expense is time and bandwidth.

  python scripts/survey_public_benchmarks.py --projects mmlu --max-sets 5
  python scripts/survey_public_benchmarks.py --out experiments/SURVEY-2026-09
"""

from __future__ import annotations

import argparse
import collections
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import item_analysis as ia  # noqa: E402

BUCKET = "https://storage.googleapis.com/crfm-helm-public"
AGENT = "RA-PSI-public-audit/1.0 (psychometric re-analysis of published results)"

# Item statistics need respondents. Below this the discrimination estimates are
# too noisy to report, and our own characterisation says a healthy item is
# falsely flagged about one time in seven at twenty respondents.
FEWEST_MODELS = 30

# HELM projects that publish per-instance results without a credential.
PROJECTS = {
    "lite": "v1.13.0",
    "classic": "v0.4.0",
    "mmlu": "v1.13.0",
}


def manifest(project: str, release: str) -> dict:
    url = "%s/%s/benchmark_output/releases/%s/runs_to_run_suites.json" % (BUCKET, project, release)
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def question_set(run_name: str) -> tuple[str, str] | None:
    """The part of a run name that decides which questions were asked.

    Everything before the model, plus the marker that introduced it. HELM writes
    that marker two ways: `scenario:subject=x,model=y` when the scenario carries
    settings, and `med_qa:model=y` when it carries none. Matching only the comma
    form drops every settings-free scenario from the survey **without saying
    so** -- which is how `med_qa`, a thousand-item medical benchmark answered by
    ninety-one models, would have been missing from a table claiming to cover
    the field. A silent exclusion is worse than a failure, because a failure is
    counted.

    Returns the question-set and the marker, so the filter handed to the
    importer reproduces the exact form the source used.
    """
    cut = run_name.rfind("model=")
    if cut < 1:
        return None
    separator = run_name[cut - 1]
    if separator not in (",", ":"):
        return None
    return run_name[:cut - 1], separator + "model="


def discover(projects: dict[str, str], fewest: int) -> tuple[list[dict], dict]:
    found = []
    skipped: dict[str, int] = {}
    for project, release in projects.items():
        names = manifest(project, release)
        counts: collections.Counter = collections.Counter()
        markers: dict[str, str] = {}
        no_model = 0
        for name in names:
            parsed = question_set(name)
            if parsed is None:
                no_model += 1
                continue
            key, marker = parsed
            counts[key] += 1
            markers[key] = marker
        skipped[project] = no_model
        for key, models in sorted(counts.items()):
            if models >= fewest:
                found.append({"project": project, "release": release, "question_set": key,
                              "marker": markers[key], "models_available": models})
    return found, {"runs_naming_no_model": skipped,
                   "note": "runs with no model= in their name take no part in an item "
                           "analysis; counted here rather than dropped quietly"}


def slug(project: str, key: str) -> str:
    safe = "".join(character if character.isalnum() else "-" for character in key)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return ("%s-%s" % (project, safe.strip("-")))[:120]


def audit_one(entry: dict, out_dir: Path, cache: Path, max_models: int | None,
              timeout: int) -> dict:
    """Import one question-set and run the item analysis over it."""
    name = slug(entry["project"], entry["question_set"])
    table = out_dir / "tables" / ("%s.csv" % name)
    provenance = out_dir / "tables" / ("%s.provenance.json" % name)
    row = {"project": entry["project"], "question_set": entry["question_set"],
           "models_available": entry["models_available"], "slug": name}

    if not table.is_file():
        command = [sys.executable, str(ROOT / "scripts" / "import_public_results.py"),
                   "--project", entry["project"], "--release", entry["release"],
                   # The trailing marker keeps `subject=algebra` from also
                   # selecting `subject=algebra_2` where such a name exists, and
                   # reproduces whichever separator the source used.
                   "--run-filter", entry["question_set"] + entry["marker"],
                   "--out", str(table), "--manifest", str(provenance),
                   "--cache", str(cache)]
        if max_models:
            command += ["--max-models", str(max_models)]
        try:
            done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            row["status"] = "failed"
            row["reason"] = "import exceeded %ds" % timeout
            return row
        if done.returncode != 0:
            row["status"] = "failed"
            # The importer's refusals are the informative part; keep the last
            # line it printed rather than a generic exit code.
            message = (done.stderr or done.stdout or "").strip().splitlines()
            row["reason"] = message[-1][:300] if message else "exit %d" % done.returncode
            return row

    try:
        rows, items = ia.from_table(table)
    except SystemExit as refusal:
        row["status"] = "failed"
        row["reason"] = str(refusal)[:300]
        return row

    if len(rows) < FEWEST_MODELS:
        row["status"] = "failed"
        row["reason"] = ("%d complete respondents after the join, below the %d this survey "
                         "reports from" % (len(rows), FEWEST_MODELS))
        return row

    per_item = ia.analyse(rows, items)
    length = ia.effective_length(per_item)
    negative = [r["item"] for r in per_item
                if r["discrimination"] is not None and r["discrimination"] < 0]
    report = {"record_version": "RA-PSI-ITEMS-V1", "source": str(table),
              "trials": len(rows), "items": len(items), "kind": "from table",
              "alpha": ia.alpha(rows, items), "effective_length": length,
              "per_item": per_item,
              "flagged": sum(1 for r in per_item if r["flags"])}
    (out_dir / "reports" / ("report-%s.json" % name)).write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    row.update({
        "status": "audited",
        "respondents": len(rows),
        "items": len(items),
        "items_carrying": length["items_carrying"],
        "share_carrying_pct": length["share_carrying_pct"],
        "items_answered_alike": length["items_all_but_a_few_answer_alike"],
        "items_running_backwards": len(negative),
        "alpha": None if report["alpha"] is None else round(report["alpha"], 3),
        "reading": length["reading"],
    })
    return row


def free_gigabytes(path: Path) -> float:
    return shutil.disk_usage(path).free / (1024 ** 3)


def prune(cache: Path) -> None:
    """Throw the downloaded JSON away once a question-set is done with it.

    Safe by construction: every file the import used is recorded in that set's
    provenance manifest with its URL and its sha256, so the cache can be
    rebuilt exactly and is never the record of anything. Keeping it is a
    convenience, and at five gigabytes per twenty-eight question-sets it stops
    being one on somebody's own laptop.
    """
    if cache.is_dir():
        shutil.rmtree(cache, ignore_errors=True)
    cache.mkdir(parents=True, exist_ok=True)


def summarise(rows: list[dict]) -> dict:
    audited = [r for r in rows if r["status"] == "audited"]
    if not audited:
        return {"audited": 0, "note": "nothing was audited, so there is nothing to summarise"}
    shares = sorted(r["share_carrying_pct"] for r in audited)
    alphas = sorted(r["alpha"] for r in audited if r["alpha"] is not None)

    def middle(values: list[float]) -> float | None:
        if not values:
            return None
        half = len(values) // 2
        return values[half] if len(values) % 2 else (values[half - 1] + values[half]) / 2

    return {
        "audited": len(audited),
        "failed": len(rows) - len(audited),
        "respondents_total_min": min(r["respondents"] for r in audited),
        "respondents_total_max": max(r["respondents"] for r in audited),
        "items_counted": sum(r["items"] for r in audited),
        "items_carrying": sum(r["items_carrying"] for r in audited),
        "share_carrying_median_pct": middle(shares),
        "share_carrying_worst_pct": shares[0],
        "share_carrying_best_pct": shares[-1],
        "alpha_median": middle(alphas),
        "sets_with_an_item_running_backwards":
            sum(1 for r in audited if r["items_running_backwards"] > 0),
        "items_running_backwards_total":
            sum(r["items_running_backwards"] for r in audited),
        "note": ("an item running backwards is one the better respondents get wrong more "
                 "often than the weaker ones; it is the signature of a wrong answer key, "
                 "and our own characterisation puts the false alarm rate for this flag "
                 "beside it in experiments/DETECTION-2026-09"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--projects", nargs="*", default=sorted(PROJECTS),
                        choices=sorted(PROJECTS))
    parser.add_argument("--out", type=Path, default=ROOT / "experiments" / "SURVEY-2026-09")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "helm")
    parser.add_argument("--max-sets", type=int, help="stop after this many question-sets")
    parser.add_argument("--max-models", type=int,
                        help="cap respondents per set; lowers download time and precision")
    parser.add_argument("--fewest-models", type=int, default=FEWEST_MODELS)
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per import")
    parser.add_argument("--pause", type=float, default=1.0, help="seconds between sets")
    parser.add_argument("--keep-cache", action="store_true",
                        help="keep downloaded JSON between sets; costs gigabytes")
    parser.add_argument("--stop-below-gb", type=float, default=15.0,
                        help="stop rather than fill the disk below this much free space")
    args = parser.parse_args()

    if args.fewest_models < 20:
        raise SystemExit(
            "%d respondents is below what this survey will report from. At twenty, our own "
            "characterisation puts the false alarm rate near one healthy item in seven "
            "(experiments/DETECTION-2026-09), and a table of such rows would read as "
            "findings." % args.fewest_models)

    for folder in ("tables", "reports"):
        (args.out / folder).mkdir(parents=True, exist_ok=True)
    args.cache.mkdir(parents=True, exist_ok=True)

    chosen = {name: PROJECTS[name] for name in args.projects}
    entries, discovery = discover(chosen, args.fewest_models)
    if args.max_sets:
        entries = entries[:args.max_sets]
    print("# %d question-sets with at least %d models"
          % (len(entries), args.fewest_models), file=sys.stderr)

    # A set already decided keeps its verdict: re-downloading gigabytes to be
    # told the same refusal twice helps nobody.
    settled = {}
    record = args.out / "survey.json"
    if record.is_file():
        try:
            for row in json.loads(record.read_text(encoding="utf-8")).get("sets", []):
                settled[row["question_set"]] = row
        except ValueError:
            settled = {}
    if settled:
        print("# %d question-sets already settled and kept" % len(settled), file=sys.stderr)

    rows = []
    for index, entry in enumerate(entries, 1):
        if entry["question_set"] in settled:
            rows.append(settled[entry["question_set"]])
            continue
        free = free_gigabytes(args.out)
        if free < args.stop_below_gb:
            print("# STOPPING: %.1f GB free, below the %.1f GB floor. %d sets not attempted."
                  % (free, args.stop_below_gb, len(entries) - index + 1), file=sys.stderr)
            break
        row = audit_one(entry, args.out, args.cache, args.max_models, args.timeout)
        rows.append(row)
        if not args.keep_cache:
            prune(args.cache)
        print("# [%d/%d] %-8s %-52s %s"
              % (index, len(entries), row["project"], row["question_set"][:52],
                 row.get("reading", row.get("reason", ""))[:60]), file=sys.stderr)
        (args.out / "survey.json").write_text(
            json.dumps({"record_version": "RA-PSI-SURVEY-V1",
                        "fewest_models": args.fewest_models,
                        "max_models_per_set": args.max_models,
                        "discovery": discovery,
                        "summary": summarise(rows), "sets": rows},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        time.sleep(args.pause)

    print(json.dumps(summarise(rows), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
