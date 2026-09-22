#!/usr/bin/env python3
"""Turn somebody else's published per-item benchmark results into our three columns.

`scripts/item_analysis.py --table` will read a CSV of trial, item, correct from
any source. Almost nothing publishes that. What a few projects do publish is
per-instance records: for one model, on one scenario, which instances it got
right. Stack enough of those on the *same* instances and the columns fall out,
with each model playing the part of a respondent.

This imports HELM (Stanford CRFM), because HELM is the only large public
benchmark found that puts per-instance correctness for many models in an
unauthenticated, listable bucket. The HuggingFace Open LLM Leaderboard
`details_*` datasets hold the same thing and are gated: they answer 401 without
a token, so they are not usable here and this script does not try.

The three joins that make this an audit rather than a guess:

- **items are matched by instance id, and the id is verified.** Two models are
  only comparable on an item if they were asked the same question. Every run's
  `instances.json` is fingerprinted — question text, every reference, and which
  reference is correct — and a run whose fingerprint for an id disagrees with
  the others is refused, not silently pooled.
- **every model must have answered every item.** `item_analysis.from_table`
  drops incomplete trials itself, but dropping them here with a named count is
  the difference between a known exclusion and a quiet one.
- **correctness must already be binary.** HELM's `exact_match` on a
  multiple-choice adapter is 0.0 or 1.0, so no threshold is chosen and none can
  be got wrong. A metric that arrives with values in between is refused rather
  than rounded, because where the cut falls would change the answer and that is
  not a decision to make inside an import.

What it refuses to do: invent an item a model did not answer, average repeats
into a fraction, threshold a continuous score, or reach for a source that wants
a credential.

  python scripts/import_public_results.py \
      --run-filter "mmlu:subject=college_chemistry" \
      --out experiments/PUBLIC-AUDIT-2026-09/helm-mmlu-college_chemistry.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BUCKET = "https://storage.googleapis.com/crfm-helm-public"
USER_AGENT = "RA-PSI-public-audit/1.0 (psychometric re-analysis of published results)"

# HELM writes one of these per run. We need the second for the numbers and the
# first to prove the numbers are about the same questions.
INSTANCES = "instances.json"
PER_INSTANCE_STATS = "per_instance_stats.json"


def fetch(url: str, cache: Path | None, attempts: int = 4) -> bytes:
    """GET with an on-disk cache, because an audit gets re-run and the bucket is a guest.

    The cache key is the URL, so a second run costs nothing and the source is
    asked once. Bytes are returned rather than parsed JSON so the caller can
    hash exactly what was served.
    """
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    cached = None if cache is None else cache / (key + ".json")
    if cached is not None and cached.is_file():
        return cached.read_bytes()
    quoted = urllib.parse.quote(url, safe=":/?&=%")
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(quoted, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=90) as response:
                body = response.read()
            break
        except (urllib.error.URLError, TimeoutError) as error:  # pragma: no cover - network
            last = error
            if isinstance(error, urllib.error.HTTPError) and error.code in (401, 403):
                raise SystemExit(
                    "%s answered %d. This source wants a credential; no credential will be "
                    "supplied. Pick a source that does not." % (url, error.code)
                )
            time.sleep(1.5 * (attempt + 1))
    else:  # pragma: no cover - network
        raise SystemExit("could not fetch %s: %s" % (url, last))
    if cached is not None:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(body)
    return body


def run_url(project: str, suite: str, run_name: str, filename: str) -> str:
    return "%s/%s/benchmark_output/runs/%s/%s/%s" % (BUCKET, project, suite, run_name, filename)


def release_manifest(project: str, release: str, cache: Path | None) -> dict:
    """Which suite directory holds each run of a release.

    HELM publishes incrementally: a release is a manifest naming, for every run
    in it, the suite version whose directory actually contains the files. Going
    straight to the newest suite directory finds only the models added last —
    four of ninety-one, in the release used here. That mistake would not fail,
    it would just quietly analyse a tiny unrepresentative slice.
    """
    url = "%s/%s/benchmark_output/releases/%s/runs_to_run_suites.json" % (BUCKET, project, release)
    return json.loads(fetch(url, cache).decode("utf-8"))


def split_run_name(run_name: str) -> tuple[str, str]:
    """A HELM run name is a scenario and a model glued with commas. Separate them."""
    parts = run_name.split(",")
    model = next((p.split("=", 1)[1] for p in parts if p.startswith("model=")), "")
    scenario = ",".join(p for p in parts if not p.startswith("model="))
    return scenario, model


def short_scenario(scenario: str) -> str:
    """A readable label for an item prefix: the subject if there is one."""
    for part in scenario.split(","):
        # The first comma-separated part carries the scenario name too, as
        # `mmlu:subject=college_chemistry`, so the key is not always at the start.
        key = part.split(":")[-1]
        if key.startswith("subject="):
            return key.split("=", 1)[1]
    return scenario.split(":", 1)[0]


def fingerprint_instances(instances: list[dict]) -> dict[str, str]:
    """Hash what each instance actually asked, so identical ids can be proven identical.

    Instance ids are positional (`id0`, `id1`, ...). Two runs sharing an id is
    not evidence they shared a question — if a scenario were resampled or
    reordered between suite versions, the ids would line up and the questions
    would not. The question text, every reference in order, and each
    reference's tags (which is where `correct` lives) all go into the hash.
    """
    out: dict[str, str] = {}
    for instance in instances:
        payload = {
            "input": (instance.get("input") or {}).get("text", ""),
            "references": [
                {"output": (ref.get("output") or {}).get("text", ""),
                 "tags": sorted(ref.get("tags") or [])}
                for ref in instance.get("references") or []
            ],
            "split": instance.get("split", ""),
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        out[str(instance["id"])] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return out


def correctness(stats: list[dict], metric: str, run_name: str) -> dict[str, int]:
    """Per-instance 0/1 for one run, refusing anything that is not already 0/1.

    HELM records one entry per (instance, train_trial_index). More than one
    trial per instance would mean the model answered the same question twice,
    and collapsing that into a single bit is a modelling decision — so it is
    refused here instead of averaged.
    """
    out: dict[str, int] = {}
    for entry in stats:
        value = next((s.get("mean") for s in entry.get("stats", [])
                      if s.get("name", {}).get("name") == metric), None)
        if value is None:
            continue
        instance = str(entry["instance_id"])
        if instance in out:
            raise SystemExit(
                "%s records %s more than once for instance %s; collapsing repeats into one "
                "bit is a decision this import will not make silently" % (run_name, metric, instance)
            )
        if value not in (0.0, 1.0, 0, 1):
            raise SystemExit(
                "%s reports %s=%r for instance %s, which is not already right-or-wrong. "
                "Choosing a threshold would change the answer; pick a binary metric."
                % (run_name, metric, value, instance)
            )
        out[instance] = int(value)
    return out


def assemble(runs: list[dict], prefix_items: bool) -> tuple[list[dict], dict]:
    """Join the runs into rows of trial, item, correct, and say what was left out.

    Returns the rows plus a note of every exclusion, because an audit that drops
    things without counting them is just a nicer-looking number.
    """
    fingerprints: dict[str, tuple[str, str]] = {}  # item -> (hash, first run that said so)
    conflicts: list[str] = []
    per_run_items: dict[str, set[str]] = {}
    scored: dict[str, dict[str, int]] = {}

    for run in runs:
        label = short_scenario(run["scenario"]) if prefix_items else None
        # One model appears once per scenario. Assigning instead of merging here
        # would keep only its last scenario and quietly drop the rest — which on
        # the five MMLU subjects would have thrown away four fifths of the data
        # while still producing a plausible-looking report.
        answers = scored.setdefault(run["model"], {})
        for instance_id, right in run["correct"].items():
            item = "%s/%s" % (label, instance_id) if label else instance_id
            seen = fingerprints.get(item)
            if seen is None:
                fingerprints[item] = (run["fingerprints"][instance_id], run["model"])
            elif seen[0] != run["fingerprints"].get(instance_id):
                conflicts.append("%s: %s asks a different question from %s"
                                 % (item, run["model"], seen[1]))
                continue
            answers[item] = right
        per_run_items[run["model"]] = set(answers)

    if conflicts:
        raise SystemExit(
            "the same item id does not hold the same question across models:\n  "
            + "\n  ".join(conflicts[:10])
            + "\nPooling these would compare models on different questions."
        )

    # The item set is the intersection: an item only some models were asked
    # cannot have a difficulty, and padding the rest with zeros would score them
    # wrong on a question nobody put to them.
    common: set[str] = set.intersection(*per_run_items.values()) if per_run_items else set()
    everything = set().union(*per_run_items.values()) if per_run_items else set()
    # Named for the model that is short of something, not for the model that has
    # more than the intersection — those are different sets and only the first
    # explains why an item was dropped.
    dropped_models = [model for model, items in per_run_items.items() if items != everything]

    rows = [{"trial": model, "item": item, "correct": answers[item]}
            for model, answers in sorted(scored.items())
            for item in sorted(common, key=sort_key)]
    notes = {
        "models": len(scored),
        "items_common_to_every_model": len(common),
        "items_seen_at_all": len(everything),
        "items_dropped_for_not_being_universal": sorted(everything - common, key=sort_key),
        "models_that_were_missing_an_item": sorted(dropped_models),
    }
    return rows, notes


def sort_key(item: str) -> tuple:
    """`id10` after `id9`, not between `id1` and `id2`."""
    head, _, tail = item.rpartition("/")
    digits = "".join(c for c in tail if c.isdigit())
    return (head, int(digits) if digits else -1, tail)


def gather(project: str, release: str, run_filter: str, metric: str,
           cache: Path | None, max_models: int | None) -> tuple[list[dict], list[dict]]:
    manifest = release_manifest(project, release, cache)
    selected = sorted((name, suite) for name, suite in manifest.items() if run_filter in name)
    if not selected:
        raise SystemExit("no run in release %s of %s matches %r" % (release, project, run_filter))
    runs: list[dict] = []
    provenance: list[dict] = []
    models_seen: set[str] = set()
    for name, suite in selected:
        scenario, model = split_run_name(name)
        if max_models is not None and model not in models_seen and len(models_seen) >= max_models:
            continue
        models_seen.add(model)
        stats_url = run_url(project, suite, name, PER_INSTANCE_STATS)
        inst_url = run_url(project, suite, name, INSTANCES)
        stats_raw = fetch(stats_url, cache)
        inst_raw = fetch(inst_url, cache)
        runs.append({
            "run": name, "suite": suite, "scenario": scenario, "model": model,
            "correct": correctness(json.loads(stats_raw.decode("utf-8")), metric, name),
            "fingerprints": fingerprint_instances(json.loads(inst_raw.decode("utf-8"))),
        })
        provenance.append({
            "run": name, "suite": suite, "model": model,
            "per_instance_stats_url": stats_url,
            "per_instance_stats_sha256": hashlib.sha256(stats_raw).hexdigest(),
            "instances_url": inst_url,
            "instances_sha256": hashlib.sha256(inst_raw).hexdigest(),
        })
        print("  %-9s %s" % (suite, name), file=sys.stderr)
    return runs, provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default="lite", help="HELM project bucket (lite, classic, ...)")
    parser.add_argument("--release", default="v1.13.0", help="HELM release whose manifest to read")
    parser.add_argument("--run-filter", required=True, help="substring every run name must contain")
    parser.add_argument("--metric", default="exact_match", help="per-instance stat to read as correctness")
    parser.add_argument("--out", type=Path, required=True, help="CSV of trial,item,correct to write")
    parser.add_argument("--manifest", type=Path, help="where to write the provenance record")
    parser.add_argument("--cache", type=Path, help="directory to keep downloaded JSON in")
    parser.add_argument("--max-models", type=int, help="stop after this many distinct models")
    parser.add_argument("--prefix-items", action="store_true",
                        help="prefix item ids with the scenario, needed when pooling scenarios")
    args = parser.parse_args()

    if args.cache:
        args.cache.mkdir(parents=True, exist_ok=True)
    runs, provenance = gather(args.project, args.release, args.run_filter,
                              args.metric, args.cache, args.max_models)
    scenarios = sorted({run["scenario"] for run in runs})
    prefix = args.prefix_items or len(scenarios) > 1
    rows, notes = assemble(runs, prefix)
    if not rows:
        raise SystemExit("nothing survived the join; refusing to write an empty table")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["trial", "item", "correct"])
        writer.writeheader()
        writer.writerows(rows)

    record = {
        "record_version": "RA-PSI-IMPORT-V1",
        "source": "HELM %s, release %s, %s" % (args.project, args.release, BUCKET),
        "run_filter": args.run_filter,
        "metric": args.metric,
        "metric_note": "already 0 or 1 in the source; no threshold was chosen",
        "scenarios": scenarios,
        "table": str(args.out),
        "rows": len(rows),
        **notes,
        "runs": provenance,
    }
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items() if k != "runs"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
