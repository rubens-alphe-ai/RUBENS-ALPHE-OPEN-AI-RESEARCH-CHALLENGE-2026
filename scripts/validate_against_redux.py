#!/usr/bin/env python3
"""Do the item flags find the answer-key errors that human experts found?

Pre-registered in `experiments/VALIDATION-REDUX-2026-10/PREREGISTRATION.md`
before the two sources were joined. This joins the survey's per-item flags for
HELM MMLU (`experiments/SURVEY-2026-09`) to the expert labels of MMLU-Redux 2.0
(CC BY 4.0) by normalised question text, and scores the four predictions.

Nothing is re-analysed: the flags are read from the stored survey reports, and
the labels from the published dataset.

  python scripts/validate_against_redux.py --out experiments/VALIDATION-REDUX-2026-10/result.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import string
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURVEY = ROOT / "experiments" / "SURVEY-2026-09"
CACHE = ROOT / ".cache" / "redux"
AGENT = "RA-PSI-public-audit/1.0 (psychometric re-analysis of published results)"
REDUX = "https://datasets-server.huggingface.co/rows?dataset=edinburgh-dawg/mmlu-redux-2.0&config=%s&split=test&offset=0&length=100"
PUNCT = re.compile("[%s]" % re.escape(string.punctuation))


def get_json(url: str, cache_name: str):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / cache_name
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
            path.write_text(json.dumps(data), encoding="utf-8")
            return data
        except Exception as exc:  # noqa: BLE001
            if attempt == 3:
                raise SystemExit("could not fetch %s: %s" % (url, exc))
            time.sleep(5 * (attempt + 1))


def normalise(text: str) -> str:
    return " ".join(PUNCT.sub(" ", text.lower()).split())


def wilson(hits: int, n: int) -> list[float] | None:
    if n == 0:
        return None
    z, p = 1.96, hits / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - s), 3), round(min(1.0, c + s), 3)]


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else None


def subjects() -> list[tuple[str, str]]:
    record = json.loads((SURVEY / "survey.json").read_text(encoding="utf-8"))
    out = []
    for row in record["sets"]:
        if row.get("status") != "audited" or not row["question_set"].startswith("mmlu:subject="):
            continue
        subject = row["question_set"].split("subject=", 1)[1].split(",", 1)[0]
        out.append((subject, row["slug"]))
    return sorted(set(out))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    items = []
    per_subject = []
    dropped = {"no_match": 0, "ambiguous": 0, "not_in_report": 0}
    for subject, slug in subjects():
        report_path = SURVEY / "reports" / ("report-%s.json" % slug)
        manifest_path = SURVEY / "tables" / ("%s.provenance.json" % slug)
        if not report_path.is_file() or not manifest_path.is_file():
            continue
        report = {r["item"]: r for r in json.loads(report_path.read_text(encoding="utf-8"))["per_item"]}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        instances = get_json(manifest["runs"][0]["instances_url"], "helm-%s.json" % subject)
        by_text: dict[str, list[str]] = {}
        for inst in instances:
            by_text.setdefault(normalise(inst["input"]["text"]), []).append(inst["id"])
        redux = get_json(REDUX % urllib.parse.quote(subject), "redux-%s.json" % subject)
        rows = [r["row"] for r in redux.get("rows", [])]
        matched = 0
        for row in rows:
            ids = by_text.get(normalise(row["question"]), [])
            if not ids:
                dropped["no_match"] += 1
                continue
            if len(ids) > 1:
                dropped["ambiguous"] += 1
                continue
            stat = report.get(ids[0])
            if stat is None:
                dropped["not_in_report"] += 1
                continue
            matched += 1
            d = stat.get("discrimination")
            items.append({
                "subject": subject, "item": ids[0], "error_type": row["error_type"],
                "key_error": row["error_type"] == "wrong_groundtruth",
                "any_error": row["error_type"] != "ok",
                "discrimination": d,
                "screening": d is not None and d < 0,
                "strict": any("negative" in f for f in stat.get("flags_confident", [])),
            })
        subj_items = [i for i in items if i["subject"] == subject]
        if subj_items:
            per_subject.append({
                "subject": subject, "matched": len(subj_items),
                "any_error_rate": sum(i["any_error"] for i in subj_items) / len(subj_items),
                "screening_rate": sum(i["screening"] for i in subj_items) / len(subj_items),
            })

    n = len(items)
    unflagged = [i for i in items if not i["screening"]]
    base_hits = sum(i["key_error"] for i in unflagged)
    base = base_hits / len(unflagged) if unflagged else None

    def enrichment(group: list[dict]) -> dict:
        hits = sum(i["key_error"] for i in group)
        rate = hits / len(group) if group else None
        return {"flagged": len(group), "key_errors": hits, "rate": None if rate is None else round(rate, 3),
                "rate_interval_95": wilson(hits, len(group)),
                "enrichment": None if (rate is None or not base) else round(rate / base, 2)}

    strict = enrichment([i for i in items if i["strict"]])
    screening = enrichment([i for i in items if i["screening"]])
    key = [i for i in items if i["key_error"]]
    recall = sum(i["screening"] for i in key) / len(key) if key else None
    rho = spearman([s["any_error_rate"] for s in per_subject], [s["screening_rate"] for s in per_subject])

    def verdict(value, threshold):
        if value is None:
            return "not computable"
        return "held" if value >= threshold else "FAILED"

    record = {
        "record_version": "RA-PSI-REDUX-VALIDATION-V1",
        "preregistration": "experiments/VALIDATION-REDUX-2026-10/PREREGISTRATION.md",
        "sources": {"flags": "experiments/SURVEY-2026-09 (HELM MMLU, up to 60 models)",
                    "labels": "MMLU-Redux 2.0, edinburgh-dawg/mmlu-redux-2.0, CC BY 4.0"},
        "matched_items": n, "subjects": len(per_subject), "dropped": dropped,
        "underpowered": n < 200,
        "key_error_rate_unflagged": None if base is None else round(base, 3),
        "key_error_rate_unflagged_interval_95": wilson(base_hits, len(unflagged)),
        "strict": strict, "screening": screening,
        "recall_of_key_errors_on_screening": None if recall is None else round(recall, 3),
        "recall_interval_95": wilson(sum(i["screening"] for i in key), len(key)),
        "key_error_items": len(key),
        "subject_spearman_any_error_vs_screening": None if rho is None else round(rho, 3),
        "predictions": {
            "P1_strict_enrichment_ge_2": verdict(strict["enrichment"], 2.0),
            "P2_screening_enrichment_ge_1_5": verdict(screening["enrichment"], 1.5),
            "P3_recall_ge_0_25": verdict(recall, 0.25),
            "P4_subject_rho_ge_0_3": verdict(rho, 0.3),
        },
        "per_subject": per_subject,
        "items": items,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    summary = {k: v for k, v in record.items() if k not in ("per_subject", "items")}
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
