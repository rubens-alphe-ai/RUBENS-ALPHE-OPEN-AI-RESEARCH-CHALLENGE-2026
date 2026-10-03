#!/usr/bin/env python3
"""Turn a claim scan into one private, personal note per organisation.

Each note gives the organisation the statistical reading of its own model
card: which of its benchmark gaps are established at the size of the test, and
which are not. It is written to be useful on its own, whether or not the
reader ever buys anything. Nothing is sent: the notes are drafts for the owner
to approve, and for whoever sends them to address.

  python scripts/claim_notes.py --scan .private/claims-scan/scan.json --out .private/claims-scan/notes.md
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

GITHUB = "https://github.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026"
CALCULATOR = "[calculator link, once shared]"

# Scores at chance level on these benchmarks mark a research toy, not a buyer.
CHANCE = {"HellaSwag": 0.30, "ARC-Challenge": 0.30, "ARC-Easy": 0.30}


def pts(x: float) -> str:
    return "%+.1f" % x


def line(model: str, c: dict) -> str:
    lo, hi = c["interval_95_pts"]
    if c["established"]:
        reading = "established"
    elif c["gap_pts"] == 0:
        reading = "no gap"
    else:
        reading = "not established at this test size"
    return ("- **%s** (%d questions): %s %s against %s %s, a gap of %s points; 95%% interval %s to %s: %s."
            % (c["benchmark"], c["questions"], model, c["this_score"], c["other_model"], c["other_score"],
               pts(c["gap_pts"]), pts(lo), pts(hi), reading))


def is_toy(record: dict) -> bool:
    for c in record["comparisons"]:
        limit = CHANCE.get(c["benchmark"])
        if limit is not None:
            score = float(str(c["this_score"]).rstrip("%").replace(",", "."))
            score = score / 100 if score > 1 else score
            if score < limit:
                return True
    return False


def note(org: str, records: list[dict]) -> str:
    main = max(records, key=lambda r: r.get("likes") or 0)
    comparisons = [(r["model"].split("/", 1)[1], c) for r in records for c in r["comparisons"]]
    ahead_open = [x for x in comparisons if x[1]["gap_pts"] > 0 and not x[1]["established"]]
    behind_open = [x for x in comparisons if x[1]["gap_pts"] < 0 and not x[1]["established"]]
    ahead_shown = [x for x in comparisons if x[1]["gap_pts"] > 0 and x[1]["established"]]

    body = ["Hi %s team," % org, "",
            "I read the model card of %s. Taking the scores in your comparison table and the size of each "
            "public test set, here is what a standard 95%% interval says about the gaps:" % main["model"], ""]
    body += [line(m, c) for m, c in comparisons]
    body.append("")
    if ahead_open:
        body.append("A gap inside its interval is not a wrong result: the test is too small to show it. A paired "
                    "comparison on your per-item results is more sensitive and often settles it. I can run it in "
                    "48 hours, and the report says plainly which way it comes out. The price is €1,500; for our "
                    "first five clients it is €750 in exchange for a short public testimonial.")
    if behind_open:
        body.append("Read the other way, the same intervals mean you are not shown to be behind on %s."
                    % ", ".join(sorted({c["benchmark"] for _, c in behind_open})))
    if not ahead_open:
        body.append("If you ever need a gap settled on your own results, the paired check takes 48 hours.")
    if ahead_shown:
        body.append("Your lead on %s holds up at this test size. If it helps, I can write that up as a short public "
                    "verification note you can link to, at no charge."
                    % ", ".join(sorted({c["benchmark"] for _, c in ahead_shown})))
    body += ["",
             "Method: unpaired comparison of two proportions, using the size of the public test set; it is the "
             "conservative reading. Free calculator: %s. Code and validation: %s." % (CALCULATOR, GITHUB),
             "",
             "If this isn't relevant, a one-word reply is enough and I won't write again.",
             "",
             "Rubens Alphe",
             "Item Audit"]
    subject = "%s: which of your benchmark gaps are established?" % main["model"].split("/", 1)[1]
    return "\n".join(["## %s" % org, "",
                      "- Models: %s" % ", ".join(r["model"] for r in records),
                      "- Priority: %s" % ("low (research-scale model)" if any(is_toy(r) for r in records) else "normal"),
                      "- Contact: to be found by Codex (published address or form only)",
                      "- Subject: %s" % subject, "", "```text", *body, "```", ""])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    scan = json.loads(args.scan.read_text(encoding="utf-8"))
    by_org: dict[str, list[dict]] = defaultdict(list)
    for record in scan["models"]:
        if record["comparisons"]:
            by_org[record["organisation"]].append(record)
    ordered = sorted(by_org.items(), key=lambda kv: (any(is_toy(r) for r in kv[1]),
                                                     -max(r.get("likes") or 0 for r in kv[1])))
    head = ["# Private notes from the claim scan of %s" % scan["summary"]["scanned_at_utc"][:10], "",
            "Drafts only. Nothing has been sent. Each note goes to one organisation, privately; none is for "
            "public use. %d organisations, %d comparisons, %d established and %d not established."
            % (len(by_org), scan["summary"]["comparisons"], scan["summary"]["established"],
               scan["summary"]["not_established"]), ""]
    args.out.write_text("\n".join(head + [note(org, recs) for org, recs in ordered]), encoding="utf-8")
    print("%d notes written to %s" % (len(by_org), args.out))


if __name__ == "__main__":
    main()
