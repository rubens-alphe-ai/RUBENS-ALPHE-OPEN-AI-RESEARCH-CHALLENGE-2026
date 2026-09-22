#!/usr/bin/env python3
"""Turn an item analysis into one page someone buying an evaluation would act on.

`item_analysis.py` prints a JSON record: an alpha, a per-item table of
difficulty and discrimination, a count of how many items are carrying the
measurement. That is the right form for a statistician and the wrong form for
the person deciding whether to keep paying for the benchmark. They need four
sentences — how many of the items measure anything, which ones are keyed wrong,
what size of difference the test can actually resolve, and what fixing it costs
— and then they need to be able to check all four without trusting whoever
wrote the page.

So the body carries no statistical vocabulary at all. No alpha, no correlation,
no discrimination, no reliability. Those live in the appendix, where they are
qualified. This is the same division `diagnose_report.py` makes, for the same
reason: a decision page that reads like a methods section gets skimmed, and a
skimmed page is where a misread number does its damage.

Two refusals, and they are the point of the file:

* **A reliability figure is never presented as a verdict on the instrument.**
  Reliability is a property of a test *and* of who sat it. This project's own
  audit put HELM Lite MMLU `computer_security` at 0.948 across 91 models and
  **−0.442** across the top 20 — the same 111 items, the same answers, both
  numbers correct. A page that prints one of those and calls the benchmark good
  or bad is wrong in a way that will embarrass whoever quotes it. So the figure
  appears once, in the appendix, next to the population it describes and next to
  that pair of numbers.

* **A contested item is never recommended for deletion on the strength of
  disagreement alone.** This project proposed exactly that, was corrected in
  public, and then found that its four most-contested questions were the four
  highest-discriminating items it had. Disagreement between respondents is what
  a working item produces. The drop list here holds only items that do not vary
  at all, and an item that still separates respondents cannot enter it however
  contested it is.

  python scripts/instrument_report.py \\
      --report experiments/PUBLIC-AUDIT-2026-09/report-computer_security-top20.json \\
      --out report/ --instrument "MMLU computer_security" \\
      --population "the 20 highest-scoring models in HELM Lite v1.13.0"
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import item_analysis as ia  # noqa: E402  (FLOOR, CEILING, WEAK — one definition, not two)

APPENDIX = "## Appendix: the statistics behind the page"

# The population sentence that must accompany every reliability figure. It is a
# constant rather than prose so that no future edit can print the number without
# it.
POPULATION_WARNING = (
    "This figure describes these respondents as much as it describes the test, and it is not a "
    "grade. The same 111 items of HELM Lite MMLU `computer_security` score 0.948 across all 91 "
    "models and **-0.442** across the top 20. Both are correct. Quote either one on its own and "
    "you are quoting the population, not the instrument."
)

UNNAMED = "the respondents in this data, who are not named in the record"


def negative_items(per_item: list[dict]) -> list[dict]:
    """Items the better performances are marked wrong on, worst first."""
    rows = [row for row in per_item
            if row.get("discrimination") is not None and row["discrimination"] < 0]
    return sorted(rows, key=lambda row: row["discrimination"])


def naming(rows: list[dict], limit: int = 6) -> str:
    """"`id21` is" / "`id3`, `id9` and 4 others are" — always naming what it can."""
    names = ["`%s`" % row["item"] for row in rows[:limit]]
    if len(rows) > limit:
        names.append("%d others" % (len(rows) - limit))
    if len(names) == 1:
        return names[0]
    return "%s and %s" % (", ".join(names[:-1]), names[-1])


def is_constant(row: dict) -> bool:
    """At or past the thresholds the whole project reads as "nobody varies"."""
    return row["difficulty"] >= ia.CEILING or row["difficulty"] <= ia.FLOOR


def to_drop(per_item: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Split the near-constant items into drop, hold-because-it-measures, and
    hold-because-the-key-is-suspect.

    A near-constant item is the obvious deletion candidate: almost every
    respondent answers it the same way, so it adds a near-fixed amount to every
    score. Two kinds are pulled back out of that list.

    The first is the refusal. **An item that still separates respondents never
    enters the drop list**, whatever else is true of it — not if it is
    contested, not if it is nearly constant, not if it is disliked. That guard
    exists because this project once proposed deleting its four most argued-over
    questions and those four turned out to be the four carrying the whole
    measurement. Being near the ceiling is not proof of being dead.

    The second is ordering, not principle. An item the better performances are
    marked wrong on is a key to check, and a key cannot be checked after the
    item has been deleted. Repair comes first; whether it is then dead is a
    question for the next run.
    """
    drop, measures, backwards = [], [], []
    for row in per_item:
        if not is_constant(row):
            continue
        value = row.get("discrimination")
        if value is not None and value >= ia.WEAK:
            measures.append(row)
        elif value is not None and value < 0:
            backwards.append(row)
        else:
            drop.append(row)
    return drop, measures, backwards


def most_disagreement(per_item: list[dict], count: int = 4) -> list[dict]:
    """The items respondents disagree about most — the contested ones.

    Ranked by how close to an even split the responses are, which is exactly
    where an item carries the most information. Named here so the page can say
    out loud that these are to be kept.
    """
    varying = [row for row in per_item if ia.FLOOR < row["difficulty"] < ia.CEILING]
    return sorted(varying, key=lambda row: abs(row["difficulty"] - 0.5))[:count]


def resolution(report: dict) -> dict | None:
    """The smallest score difference this instrument can tell apart.

    Derived from what the record already carries, so the page needs no data the
    analysis did not print. Cronbach's alpha relates the spread of total scores
    to the spread of the individual items:

        alpha = k/(k-1) * (1 - sum(item variance) / total variance)

    Every item's variance follows from its difficulty and the number of
    respondents, so the total variance can be recovered, and from it the
    standard error of a single score, sd * sqrt(1 - alpha). Two scores are
    conventionally called distinguishable when they differ by more than
    1.96 * sqrt(2) standard errors.

    Returns None rather than a number when alpha is missing or not above zero.
    An alpha at or below zero means the items disagree with each other more than
    chance would produce; there is no scale left to measure a difference in, and
    an interval computed from it would be arithmetic dressed as a finding.
    """
    alpha = report.get("alpha")
    per_item = report.get("per_item") or []
    k, trials = len(per_item), report.get("trials", 0)
    if alpha is None or alpha <= 0 or k < 2 or trials < 2:
        return None
    item_variance = sum(p * (1 - p) * trials / (trials - 1)
                        for p in (row["difficulty"] for row in per_item))
    remainder = 1.0 - alpha * (k - 1) / k
    if remainder <= 0:
        return None
    total_sd = math.sqrt(item_variance / remainder)
    sem = total_sd * math.sqrt(1 - alpha)
    least = 1.96 * math.sqrt(2) * sem
    return {"total_sd_items": total_sd, "standard_error_items": sem,
            "least_distinguishable_items": least,
            "least_distinguishable_pct": 100.0 * least / k}


def render(report: dict, instrument: str | None = None, population: str | None = None) -> str:
    if str(report.get("record_version", "")).startswith("RA-PSI-GRADED"):
        raise SystemExit("this reads the right/wrong record from item_analysis.py; a graded "
                         "record from graded_items.py has means instead of difficulties and "
                         "would be misread item by item")

    per_item = report["per_item"]
    length = report["effective_length"]
    counted, carrying = length["items_counted"], length["items_carrying"]
    constant = length["items_all_but_a_few_answer_alike"]
    trials = report["trials"]
    name = instrument or report.get("source") or "this test"
    who = population or UNNAMED
    backwards = negative_items(per_item)
    droppable, held_measuring, held_backwards = to_drop(per_item)
    contested = most_disagreement(per_item)
    res = resolution(report)
    # The record is written on whatever machine ran the analysis; a reader
    # pasting a Windows path into a shell gets a silently different command.
    recompute = str(report.get("source", "<your table>")).replace("\\", "/")

    lines = ["# What %s measures, and what it cannot" % name, "",
             "Read from %d responses to %d items on %s. The population is %s."
             % (trials, counted, datetime.now(timezone.utc).strftime("%Y-%m-%d"), who), ""]

    lines += ["## The short version", "",
              "- This is **a test of %d items that measures with %d**. The other %d are counted "
              "in the score and carry nothing." % (counted, carrying, counted - carrying)]
    if constant:
        lines.append("- **%d items are answered the same way by all but at most one respondent "
                     "in twenty.** They add the same amount to almost everybody's score. "
                     "Removing them would change almost no one's standing." % constant)
    if backwards:
        lines.append("- **%d items run backwards: the better performances are the ones marked "
                     "wrong on them.** That is almost never a hard question. It is almost always "
                     "a wrong answer key." % len(backwards))
    else:
        lines.append("- No item runs backwards. On every item, the respondents who do better "
                     "overall are the ones marked right.")
    if res:
        lines.append("- It cannot tell two respondents apart unless they differ by more than "
                     "**%.1f of the %d items — %.1f points out of 100**. A gap smaller than that "
                     "is not a small lead; it is a gap this test cannot see."
                     % (res["least_distinguishable_items"], counted,
                        res["least_distinguishable_pct"]))
    else:
        lines.append("- **It cannot resolve any difference between these respondents at all.** "
                     "The items disagree with each other more than chance would produce, so "
                     "there is no consistent scale left on which to call one respondent ahead "
                     "of another. Ranking these respondents on this test ranks noise.")
    lines.append("")

    if backwards:
        lines += ["## The items where the better performances are marked wrong", "",
                  "On each of these, the respondents who do well on everything else are the ones "
                  "recorded as failing. Read the question and the key before reading anything "
                  "into the score: in this project's audit of MMLU, five items with this shape "
                  "were checked by hand and five were keyed to the wrong answer.", "",
                  "| Item | Marked right for | How far it runs backwards |", "|---|---|---|"]
        for row in backwards[:12]:
            lines.append("| `%s` | %.0f%% of respondents | %.2f |"
                         % (row["item"], 100.0 * row["difficulty"], row["discrimination"]))
        if len(backwards) > 12:
            # Naming them rather than counting them: a page that says "and 6
            # more" has told the reader there is work it will not let them do.
            rest = backwards[12:]
            lines += ["", "%s, in the same order: %s."
                      % ("One more" if len(rest) == 1 else "The remaining %d" % len(rest),
                         ", ".join("`%s`" % row["item"] for row in rest))]
        lines += ["", "A value of 0 would mean the item is unrelated to the rest of the test. "
                  "-1 would mean it is exactly reversed. Anything below 0 is a question that "
                  "punishes the respondents the rest of the test rewards.", ""]

    lines += ["## What this test can and cannot tell apart", ""]
    if res:
        lines += ["Two systems that differ by **%.1f points out of 100 or less** are, on this "
                  "test, the same system. The measurement is not precise enough to separate "
                  "them, and repeating the run will not help: the imprecision is in the items, "
                  "not in the sampling." % res["least_distinguishable_pct"], "",
                  "In practice: a three-point difference on a leaderboard built from this "
                  "instrument %s."
                  % ("is inside the noise and means nothing"
                     if res["least_distinguishable_pct"] >= 3.0
                     else "is outside the noise, and is the smallest gap that is"), "",
                  "Comparisons this test *can* support are ones where the gap is larger than "
                  "that. Comparisons it cannot support include any ranking of systems clustered "
                  "within it, however many decimal places the scores are printed to.", ""]
    else:
        lines += ["Nothing. On this population the items do not agree with one another, so the "
                  "total score is not measuring a single thing that could be more or less "
                  "present in one respondent than another.", "",
                  "This is a statement about this test **with these respondents**. The same "
                  "items may separate a wider field perfectly well — see the appendix. What it "
                  "rules out is using this score to rank this population.", ""]

    lines += ["## What it would cost to fix", ""]
    if backwards:
        lines.append("**Repair %d items.** Someone reads the question and the recorded correct "
                     "answer for each of the items listed above. In this project's audit "
                     "the failure was usually visible in under a minute: the key named an option "
                     "that is plainly not the answer. Repairing a key costs one reading and "
                     "returns the item to the test."
                     % len(backwards))
        lines.append("")
    if droppable:
        share = 100.0 * len(droppable) / counted if counted else 0.0
        lines.append("**Drop %d of those %d items.** Respondents answer these the same way, so "
                     "they contribute an almost fixed amount to every score. Removing them cuts "
                     "**%.0f%% of the runs** — and with them %.0f%% of the compute, the money "
                     "and the waiting — while every respondent keeps the same standing relative "
                     "to every other. This is the rare saving that costs nothing."
                     % (len(droppable), constant, share, share))
        if held_measuring:
            many = len(held_measuring) > 1
            lines.append("")
            lines.append("%s %s held back from that list, because %s still %s respondents "
                         "despite being answered the same way by almost all of them. Nearly "
                         "unanimous is not proof of dead, and this page does not put an item "
                         "that measures onto a deletion list."
                         % (naming(held_measuring), "are" if many else "is",
                            "they" if many else "it", "separate" if many else "separates"))
        if held_backwards:
            many = len(held_backwards) > 1
            lines.append("")
            lines.append("%s %s also held back, for a different reason: %s in the repair list "
                         "above. A key cannot be checked after the item has been deleted, so "
                         "repair comes first and deletion is a question for the next run."
                         % (naming(held_backwards), "are" if many else "is",
                            "they are" if many else "it is"))
        lines.append("")
    if contested:
        lines.append("**Keep the contested items.** The items respondents disagree about most "
                     "here are %s. They will be the ones that generate arguments, and they are "
                     "the ones doing the measuring; an item everyone agrees about tells you "
                     "nothing about anyone. This project proposed deleting its own four most "
                     "argued-over questions, was corrected in public, and then found that those "
                     "four were the four highest-discriminating items in the instrument. "
                     "Disagreement is not evidence that an item is broken."
                     % ", ".join("`%s`" % row["item"] for row in contested))
        lines.append("")
    if not backwards and not droppable:
        lines.append("Nothing needs repairing and nothing can be dropped without losing "
                     "information. That is an unusual result and worth checking against the "
                     "appendix before relying on it.")
        lines.append("")

    lines += ["## How to disprove this page", "",
              "Nothing above is a judgement about the questions. Every line is arithmetic on "
              "the recorded responses, and the arithmetic is one command:", "",
              "```", "python scripts/item_analysis.py --table %s" % recompute, "```", "",
              "Three ways this page can be shown to be wrong, in the order they are worth "
              "trying:", "",
              "1. **Read the items in the backwards table.** If their keys are right, the "
              "explanation offered here is wrong and something else is producing the pattern.",
              "2. **Run it again on a different set of respondents.** Every number here depends "
              "on who answered. A wider or narrower field will produce different ones, and the "
              "appendix says how much that matters.",
              "3. **Check the arithmetic.** The command above recomputes every figure on this "
              "page from the same responses, and this page cites nothing it did not print.", ""]

    lines += [APPENDIX, "",
              "| | |", "|---|---|",
              "| Respondents | %d |" % trials,
              "| Items counted | %d |" % counted,
              "| Items carrying the measurement | %d |" % carrying,
              "| Items answered the same way by all but one respondent in twenty | %d |" % constant,
              "| Items with negative discrimination | %d |" % len(backwards),
              "| Cronbach's alpha | %s |" % ("not defined on this data" if report.get("alpha") is None
                                             else "%.3f" % report["alpha"]),
              ""]
    lines += [POPULATION_WARNING, "", ]
    if res:
        lines += ["The resolution in the body is the standard error of a single total score, "
                  "%.2f items, multiplied by 1.96 * sqrt(2) to give the smallest difference "
                  "between two scores that is distinguishable at the conventional 95%% level. "
                  "The total-score spread it rests on, %.2f items, is recovered from alpha and "
                  "the per-item difficulties rather than measured directly, because the record "
                  "this page reads does not carry per-respondent totals. It inherits every "
                  "dependence alpha has on the population above."
                  % (res["standard_error_items"], res["total_sd_items"]), ""]
    else:
        lines += ["No resolution is quoted because alpha is not above zero, and an interval "
                  "derived from it would be arithmetic dressed as a finding.", ""]
    lines += ["An item counts as carrying the measurement when at least one respondent gets it "
              "right, at least one gets it wrong, and it agrees with the rest of the test at a "
              "correlation of %.2f or better. \"Every respondent\" is read at the %.0f%% and "
              "%.0f%% thresholds, so an item that one respondent of a hundred answers differently "
              "is still counted as constant."
              % (ia.WEAK, 100 * ia.FLOOR, 100 * ia.CEILING), "",
              "Respondents are assumed independent. Where they are not — language models sharing "
              "base weights, graders trained together, students from one class — the agreement "
              "between items is inflated and every figure here is an upper bound.", ""]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", type=Path, required=True,
                        help="the JSON printed by scripts/item_analysis.py; - for stdin")
    parser.add_argument("--out", type=Path, required=True, help="folder to write REPORT.md into")
    parser.add_argument("--instrument", help="what to call the test in the heading")
    parser.add_argument("--population", help="who sat it. Name them: every number on the page "
                                             "depends on this and the page says so.")
    args = parser.parse_args()

    text = sys.stdin.read() if str(args.report) == "-" else args.report.read_text(encoding="utf-8")
    report = json.loads(text)
    page = render(report, args.instrument, args.population)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "REPORT.md").write_text(page, encoding="utf-8")
    print(json.dumps({"out": str(args.out / "REPORT.md"),
                      "reading": report["effective_length"]["reading"],
                      "items_running_backwards": len(negative_items(report["per_item"])),
                      "population_named": bool(args.population)}, indent=2))


if __name__ == "__main__":
    main()
