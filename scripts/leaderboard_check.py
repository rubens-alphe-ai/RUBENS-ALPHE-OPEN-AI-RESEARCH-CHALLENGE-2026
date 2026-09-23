#!/usr/bin/env python3
"""What a leaderboard can prove about itself, using only the leaderboard.

The audit this project sells needs per-item, per-model correctness: which model
got which question right. Almost nobody has that to hand, and extracting it
costs a day before anything is visible in return. So this file answers a smaller
question from the thing everyone already has open in a browser tab -- a column
of model names and a column of scores -- and it answers it without asking for a
credential, a dataset or an email address.

The smaller question is this. A score is a count of right answers over a fixed
number of items, so it carries a sampling error, and that error is computable
from the score and the item count alone: sqrt(p(1-p)/n). Once you have it you
can ask whether the gaps on the leaderboard are bigger than the error in the
measurement that produced them. Very often, at the top, they are not -- and a
ranking whose neighbouring gaps are smaller than its own measurement error is
not a ranking. It is a list in an order that a re-run would change.

That is a real finding and it is free. It is also, and this is the point of the
file, **not the audit**. Everything below is arithmetic on aggregate scores.
Aggregate scores cannot see inside the test, so this check cannot tell you:

- **which items are keyed to the wrong answer.** The signature is an item the
  better models are marked wrong on. It needs per-item responses. In this
  project's audit of MMLU, five items with that shape were read by hand and
  five were keyed wrong.
- **which items are dead** -- passed or failed by everyone, contributing a
  constant to every score and separating nobody.
- **the effective length** -- how many of the items counted in the score are
  measuring anything at all. This project's own quiz declares 32 fact questions
  and measures with 5.

Those three are what `scripts/item_analysis.py` reads out of a CSV of
trial, item, correct. This file names them rather than implying it covers them,
because a free check that lets a reader believe they have been audited has done
more damage than one that refuses to run.

Two refusals it is worth knowing about before reading the output:

1. **The item count is required.** Without n there is no sampling error and not
   one sentence below can be written. It is never assumed, never inferred from
   the number of models, and never defaulted.
2. **A leaderboard whose scores all sit at or below 1.0 is refused, not
   guessed at.** Those numbers are either proportions or percentages of a
   benchmark nobody scores above 1% on, and the two readings differ by a factor
   of one hundred in every figure this file prints. Declare it with --scale.

  python scripts/leaderboard_check.py --table leaderboard.csv --items 14042
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The conventional two-sided 95% multiplier. Named rather than inlined so the
# report can print it and a reader can see which bar is being cleared.
Z95 = 1.959963985

# How many of the leading models the compression paragraph is written about.
# Twenty because that is the length of a leaderboard screenshot, not because
# twenty is statistically special.
TOP = 20

# The three things this check cannot establish, carried as data rather than as
# prose so that no future edit can print the findings without printing these
# beside them.
CANNOT_ESTABLISH = [
    ("items keyed to the wrong answer",
     "The signature is an item that the models scoring well overall are marked wrong on. "
     "That is a fact about one item and many models, and an aggregate score has already "
     "added it away. It needs per-item responses."),
    ("dead items",
     "An item every model passes, or every model fails, adds the same amount to every score "
     "and separates nobody. It is invisible in the total it inflates."),
    ("effective length",
     "How many of the n items counted in the score are measuring anything. A test can report "
     "its length in items and measure with a fraction of them; nothing in an aggregate score "
     "says which fraction."),
]

WHAT_THE_AUDIT_ADDS = (
    "All three need one table: trial, item, correct -- one row per model per item. "
    "`scripts/item_analysis.py` reads that table and reports difficulty, discrimination and "
    "effective length per item; `scripts/instrument_report.py` turns it into a page. This file "
    "reads two columns and can do none of it."
)


def finite(raw: object, what: str) -> float:
    value = float(str(raw).strip())
    if not math.isfinite(value):
        raise SystemExit("%s is %r, which is not a finite number" % (what, raw))
    return value


def required_items(raw: object) -> int:
    """The item count, or an exit explaining why nothing can be said without it.

    Deliberately not an argparse `type=int` with `required=True`: a reader who
    runs this without --items is told what the flag is for, because "the
    following arguments are required" teaches them nothing and they will guess
    a number.
    """
    if raw is None:
        raise SystemExit(
            "--items is required and is never assumed. Every sentence this check can write "
            "rests on the sampling error of a score, sqrt(p(1-p)/n), and n is the number of "
            "items in the benchmark. Without it there is no error to compare the gaps to, and "
            "a leaderboard on its own cannot say whether a one-point lead is a lead or a "
            "rounding of noise. The number is published beside almost every benchmark: MMLU "
            "is 14042 questions, GSM8K's test split is 1319. Pass --items 14042.")
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        raise SystemExit(
            "--items was given %r, which is not a whole number of items. Give the count of "
            "questions in the benchmark as a plain integer, for example --items 1319." % raw)
    if value < 1:
        raise SystemExit(
            "--items was given %d. A benchmark of fewer than one item has no score to have an "
            "error in, and sqrt(p(1-p)/n) is undefined at n=0. If the suite really is that "
            "small there is nothing here to check: state the count of questions actually "
            "asked, at least 1." % value)
    return value


def resolve_scale(values: list[float], declared: str | None) -> tuple[float, str]:
    """Decide whether the score column is 0-1 or 0-100, or refuse to decide.

    This is the one place a wrong guess would change every number in the report
    by a factor of one hundred, in the direction that makes a bad leaderboard
    look precise: read 0.873 as a percentage and the sampling error comes out a
    hundred times too small, so every gap clears it and the check reports an
    ordering it has no grounds to support.

    So there are exactly two cases. A score above 1.0 cannot be a proportion,
    which settles it with no judgement required. A column that sits entirely at
    or below 1.0 is consistent with both readings -- proportions, or percentages
    of a benchmark whose best model scores under one percent -- and that is
    refused rather than resolved by plausibility, because plausibility is
    exactly the kind of reasoning that is right until the day it is not.
    """
    biggest = max(values)
    if declared is not None:
        limit = 1.0 if declared == "proportion" else 100.0
        return limit, declared
    if biggest > 1.0:
        # Nothing to weigh up: no proportion exceeds 1.
        return 100.0, "percent"
    raise SystemExit(
        "every score in this file is at or below 1.0, and that is ambiguous rather than "
        "obvious. It reads as proportions (a top score of %s means %s%% correct), and it also "
        "reads as percentages (a top score of %s means %s%% correct, on a benchmark nobody "
        "beats one percent on). The two differ by a factor of a hundred in the sampling error, "
        "which is the only thing this check computes, so guessing here would not be a rounding "
        "-- it would be the whole answer. Declare it: --scale proportion, or --scale percent."
        % (_trim(biggest), _trim(biggest * 100), _trim(biggest), _trim(biggest)))


def _trim(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else ("%g" % value)


def read_leaderboard(path: Path, declared: str | None = None) -> tuple[list[dict], str]:
    """Model names and scores from a two-column table, as proportions.

    Same column-naming tolerance as `item_analysis.from_table`, for the same
    reason: this has to run on a CSV somebody pasted out of a web page without
    them renaming anything first.
    """
    raw_rows: list[tuple[str, float]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or len(reader.fieldnames) < 2:
            raise SystemExit("%s needs a header row with a model column and a score column" % path)
        names = {name.strip().lower(): name for name in reader.fieldnames}

        def column(*candidates: str) -> str:
            for candidate in candidates:
                if candidate in names:
                    return names[candidate]
            raise SystemExit("%s has no column named any of %s; found %s"
                             % (path, " / ".join(candidates), ", ".join(reader.fieldnames)))

        model_col = column("model", "model_name", "system", "name", "submission",
                           "entry", "method", "run")
        score_col = column("score", "accuracy", "acc", "result", "value", "mean",
                           "exact_match", "percent", "pct", "performance", "correct")
        for line in reader:
            model = str(line[model_col]).strip()
            if not model:
                continue
            try:
                score = finite(line[score_col], "the score for %r" % model)
            except ValueError:
                raise SystemExit(
                    "cannot read %r as a score for %r. This reads a leaderboard: one row per "
                    "model, with a numeric aggregate score. A cell holding a rank, a date, a "
                    "confidence interval or an empty placeholder is not a score, and this file "
                    "will not parse one out of it." % (line[score_col], model))
            raw_rows.append((model, score))

    if not raw_rows:
        raise SystemExit("%s has a header row and no models under it" % path)

    seen: dict[str, float] = {}
    for model, score in raw_rows:
        if model in seen:
            # Two rows for one name may be two settings, two dates or one
            # duplicated paste. Whichever it is, every count below -- how many
            # models tie with the leader, how many orderings are unsupported --
            # would be computed on a field that does not exist.
            raise SystemExit(
                "%r appears twice in %s, scored %s and %s. This check counts models: how many "
                "cannot be separated from the leader, how many orderings the scores do not "
                "support. A name listed twice makes both counts wrong. Give each row a "
                "distinguishing name, or keep one of them."
                % (model, path, _trim(seen[model]), _trim(score)))
        seen[model] = score

    # Counted before the scale is settled, because how many models are on the
    # board is knowable without deciding what the numbers mean, and a two-row
    # file should be told it is a two-row file rather than argued with about
    # percentages.
    if len(raw_rows) < 3:
        raise SystemExit(
            "%s holds %d model%s. A leaderboard of fewer than three is not a ranking with a "
            "shape to check -- there is at most one gap, no cluster at the top and no field to "
            "be indistinguishable from. Compare two scores by hand against the error this "
            "check would print, or bring the rest of the board."
            % (path, len(raw_rows), "" if len(raw_rows) == 1 else "s"))

    limit, scale = resolve_scale([score for _model, score in raw_rows], declared)
    rows = []
    for model, score in raw_rows:
        if not (0.0 <= score <= limit):
            raise SystemExit(
                "%r scores %s, which is outside 0 to %s. Read as %s these scores are not "
                "scores, and clamping one into range would pick a winner between the file and "
                "the declaration without saying so."
                % (model, _trim(score), _trim(limit), scale))
        rows.append({"model": model, "score": score / limit, "reported": score})

    rows.sort(key=lambda row: row["score"], reverse=True)
    return rows, scale


def standard_error(p: float, n: int) -> float:
    """The binomial sampling error of a score of p over n right/wrong items."""
    return math.sqrt(max(p * (1.0 - p), 0.0) / n)


def difference_error(a: float, b: float, n: int) -> float:
    """The error on the gap between two scores, treating the two as independent.

    Two models sat the same items, so their scores are positively correlated and
    the true error on the difference is smaller than this. The test that uses
    that correlation -- McNemar's, on the items where exactly one of the two was
    right -- needs the per-item table this file does not have, which is the
    cleanest illustration in the whole report of where the free check stops.

    Using the wider figure means this check calls fewer pairs separable than a
    paired test would, so every "cannot be ordered" count below is a count that
    a paired test could only shrink. The report says so.
    """
    return math.sqrt(standard_error(a, n) ** 2 + standard_error(b, n) ** 2)


def check(rows: list[dict], items: int, top: int = TOP) -> dict:
    """Everything the two columns and the item count support, and nothing else."""
    n = items
    for row in rows:
        row["standard_error"] = standard_error(row["score"], n)

    leader = rows[0]
    tied = []
    for row in rows[1:]:
        gap = leader["score"] - row["score"]
        if gap < Z95 * difference_error(leader["score"], row["score"], n):
            tied.append(row["model"])

    pairs = []
    for above, below in zip(rows, rows[1:]):
        gap = above["score"] - below["score"]
        err = difference_error(above["score"], below["score"], n)
        pairs.append({"above": above["model"], "below": below["model"],
                      "gap_pct": 100.0 * gap,
                      "difference_error_pct": 100.0 * err,
                      "inside_one_error": gap < err,
                      "separated_at_95": gap >= Z95 * err})

    size = min(top, len(rows))
    group = rows[:size]
    span = group[0]["score"] - group[-1]["score"]
    span_err = difference_error(group[0]["score"], group[-1]["score"], n)
    group_pairs = pairs[:size - 1]
    unsupported = sum(1 for pair in group_pairs if not pair["separated_at_95"])

    typical = sorted(row["standard_error"] for row in group)[len(group) // 2]
    extremes = [row["model"] for row in rows if row["score"] in (0.0, 1.0)]

    return {
        "record_version": "RA-PSI-LEADERBOARD-V1",
        "models": len(rows),
        "items": n,
        "leader": {"model": leader["model"],
                   "score_pct": 100.0 * leader["score"],
                   "standard_error_pct": 100.0 * leader["standard_error"]},
        "typical_standard_error_pct": 100.0 * typical,
        "indistinguishable_from_the_leader": {
            "count": len(tied),
            "models": tied,
            "share_of_field_pct": 100.0 * len(tied) / (len(rows) - 1),
            "rank_one_group": len(tied) + 1,
            "reading": ("%d of the %d other models on this board cannot be separated from %s "
                        "at 95%%" % (len(tied), len(rows) - 1, leader["model"]))},
        "adjacent_pairs": {
            "pairs": len(pairs),
            "inside_one_standard_error": sum(1 for pair in pairs if pair["inside_one_error"]),
            "not_separated_at_95": sum(1 for pair in pairs if not pair["separated_at_95"]),
            "reading": ("%d of %d neighbouring pairs are closer together than the error on the "
                        "difference between them"
                        % (sum(1 for pair in pairs if pair["inside_one_error"]), len(pairs)))},
        "top_group": {
            "requested": top,
            "size": size,
            "span_pct": 100.0 * span,
            "span_in_errors": (span / span_err) if span_err else None,
            "orderings": len(group_pairs),
            "orderings_unsupported": unsupported,
            "whole_group_unorderable": span < Z95 * span_err,
            "reading": ("the top %d are spread over %.2f points, and %d of the %d orderings "
                        "inside that group are not supported by the scores"
                        % (size, 100.0 * span, unsupported, len(group_pairs)))},
        "scores_at_the_ends_of_the_range": extremes,
        "pairs": pairs,
        "cannot_establish": [{"claim": name, "why": why} for name, why in CANNOT_ESTABLISH],
        "what_the_audit_adds": WHAT_THE_AUDIT_ADDS,
    }


def render(found: dict, source: str, scale: str, benchmark: str | None = None) -> str:
    name = benchmark or source
    lead = found["leader"]
    tie = found["indistinguishable_from_the_leader"]
    adj = found["adjacent_pairs"]
    top = found["top_group"]
    n, k = found["items"], found["models"]
    compressed = (top["whole_group_unorderable"] or top["orderings_unsupported"] > 0
                  or (top["span_in_errors"] is None and top["span_pct"] > 0))

    lines = [
        "# What this leaderboard can and cannot tell you", "",
        "Read from `%s`: %d models, scored on %d items, with the score column read as %s. "
        "Every score below is printed out of 100 whichever way the file wrote it."
        % (source.replace("\\", "/"), k, n,
           "proportions, 0 to 1" if scale == "proportion" else "percentages, 0 to 100"),
        "",
        "Everything below is arithmetic on the two columns you already have. That is the point "
        "of it and it is also its limit: an aggregate score has added away everything about the "
        "individual questions, so this page can say whether the ranking holds and it cannot say "
        "anything about the test's contents. The second section says what that costs you.",
        "",
        "## What the scores establish", "",
    ]

    lines.append(
        "- **A score on %d items carries a sampling error of about %.2f points.** That is "
        "sqrt(p(1-p)/n) at the scores near the top of this board. It is not a property of any "
        "model; it is the width of the ruler."
        % (n, found["typical_standard_error_pct"]))

    if tie["count"]:
        lines.append(
            "- **%d of the %d other models cannot be told apart from %s** (scoring %.2f), at "
            "the conventional 95%% level. That is not a claim that they are equal to it. It is "
            "that these scores do not establish which is ahead, so which of those names prints "
            "at the top is decided by the sample of questions as much as by the models."
            % (tie["count"], k - 1, lead["model"], lead["score_pct"]))
    else:
        lines.append(
            "- **Every other model on this board is separated from %s** (scoring %.2f) at the "
            "conventional 95%% level. The lead is larger than the measurement error that "
            "produced it." % (lead["model"], lead["score_pct"]))

    lines.append(
        "- **%d of the %d neighbouring pairs are closer together than the error on their own "
        "difference**, and %d of the %d are not separated at 95%%. A pair in that state is "
        "printed in an order, and the order is not a finding."
        % (adj["inside_one_standard_error"], adj["pairs"],
           adj["not_separated_at_95"], adj["pairs"]))

    if top["span_pct"] == 0:
        lines.append(
            "- **The top %d all hold the same score**, so there is no ordering among them to "
            "support or refute." % top["size"])
    elif top["span_in_errors"] is None:
        # Both ends of the group sit at 0 or 100, where the normal
        # approximation puts zero error on a score. Reporting a spread of
        # infinitely many errors would be the approximation's failure printed
        # as a finding.
        lines.append(
            "- **The top %d are spread over %.2f points, and the error on that spread cannot be "
            "quoted.** Both ends of the group sit at exactly 0 or 100, where this normal "
            "approximation puts zero error on a score -- which is the one place it is known to "
            "be wrong. Treat the group as unordered until something with per-item data says "
            "otherwise." % (top["size"], top["span_pct"]))
    elif top["whole_group_unorderable"]:
        lines.append(
            "- **The top %d are spread over %.2f points, which is %.1f times the error on that "
            "very spread.** The distance from first to %dth is inside the noise, so this "
            "benchmark does not order the leading group at all -- not the neighbours, and not "
            "the ends. %d of the %d orderings inside the group are unsupported."
            % (top["size"], top["span_pct"], top["span_in_errors"], top["size"],
               top["orderings_unsupported"], top["orderings"]))
    else:
        lines.append(
            "- **The top %d are spread over %.2f points, %.1f times the error on that spread.** "
            "First and %dth are genuinely apart. Inside the group, %d of the %d orderings are "
            "still unsupported at 95%%."
            % (top["size"], top["span_pct"], top["span_in_errors"], top["size"],
               top["orderings_unsupported"], top["orderings"]))
    lines.append("")

    lines += ["## What this is not: it is not an audit of the benchmark", "",
              "This check has seen model names and totals. It has not seen a single question, "
              "a single answer, or which model got which item right. Three things that decide "
              "whether a benchmark is worth running are therefore outside it entirely, and no "
              "amount of care with the arithmetic above brings them into reach:", ""]
    for entry in found["cannot_establish"]:
        lines.append("- **%s.** %s" % (entry["claim"][0].upper() + entry["claim"][1:],
                                       entry["why"]))
    lines += ["", found["what_the_audit_adds"], "",
              "If you read one thing off this page, read that list. A free check that lets you "
              "believe you have audited your benchmark has cost you more than it gave you.", ""]

    lines += ["## What the compression does and does not license you to say", ""]
    if compressed:
        lines += [
            "The leading models cluster inside the measurement error. That licenses one "
            "sentence: **the ordering among them is not supported by these scores**, so a "
            "release note, a purchasing decision or a headline that turns on which of them is "
            "first is turning on noise.",
            "",
            "It licenses nothing about the benchmark. Clustering has at least three causes and "
            "this data cannot separate them:",
            "",
            "1. **The models really are that close.** A mature capability measured well will "
            "produce a tight board, and a tight board is then the correct answer, not a defect.",
            "2. **The test is at its ceiling.** If most items are passed by everyone, scores "
            "compress at the top whatever the models do.",
            "3. **The test is too short, or too few of its items measure anything.** %d items "
            "buys a certain resolution and no more." % n,
            "",
            "Cause 1 is a fact about the models and is good news. Causes 2 and 3 are facts about "
            "the instrument. **Telling them apart needs per-item data** -- it is exactly the "
            "difficulty and effective-length reading named in the section above. Until someone "
            "runs that, 'the models are clustered' is a statement about the leaderboard and not "
            "a verdict on the benchmark, and this page does not offer one.", ""]
    else:
        lines += [
            "The gaps on this board are larger than the error that produced them, so the "
            "ordering stands on its own. **Nothing here is an accusation.** This check found "
            "the leaderboard's ranking supported at the places it looked, and it is reporting "
            "that rather than manufacturing a concern out of it.",
            "",
            "It is also a narrow clean bill. The ordering surviving its own sampling error says "
            "nothing about whether the items are keyed correctly, whether most of them measure "
            "anything, or whether the n items are really n independent measurements. Those are "
            "the questions in the section above, and they are still open.", ""]

    lines += ["## The assumptions every number above rests on", "",
              "- **Items are independent and scored right or wrong.** sqrt(p(1-p)/n) is the "
              "error of n independent coin flips. Benchmark items are not independent: they "
              "share topics, templates, source documents and translations of the same stem. "
              "Where they are correlated, the effective number of independent items is smaller "
              "than %d, the true error is **larger** than the figure above, and every tie "
              "reported here is an undercount. This check cannot measure that correlation -- "
              "measuring it needs the per-item table." % n,
              "- **Models are treated as independent of each other**, which is why the error on "
              "a difference here is the wider, unpaired one. Two models sat the same questions, "
              "so a paired test on the items they disagree about would have more power. It also "
              "needs per-item data. That makes the counts above conservative in this one "
              "direction: a paired test could only find *fewer* pairs tied.",
              "- **Every score is read as a plain proportion of %d attempted items.** A "
              "leaderboard whose entries were scored on different subsets, with different "
              "numbers of shots, or averaged over sub-tasks, is not that, and the error is then "
              "a rough figure rather than the exact one." % n,
              "- **No correction is made for the number of comparisons.** Each pair is tested at "
              "95%% on its own. Across %d pairs some will clear that bar by luck, which pushes "
              "the tie counts down rather than up." % adj["pairs"]]
    if found["scores_at_the_ends_of_the_range"]:
        lines.append(
            "- **%s %s a score of exactly 0 or 100.** The normal approximation puts zero error "
            "on such a score, which is wrong -- it is the known failure of this interval at the "
            "ends of the range. Comparisons involving %s are optimistic."
            % (", ".join("`%s`" % model for model in found["scores_at_the_ends_of_the_range"]),
               "has" if len(found["scores_at_the_ends_of_the_range"]) == 1 else "have",
               "it" if len(found["scores_at_the_ends_of_the_range"]) == 1 else "them"))
    lines.append("")

    lines += ["## How to check this page", "",
              "Nothing above was looked up or estimated. Every figure is your own two columns "
              "and the item count you supplied, so it recomputes in one command:", "",
              "```", "python scripts/leaderboard_check.py --table %s --items %d --scale %s%s"
              % (source.replace("\\", "/"), n, scale,
                 "" if top["requested"] == TOP else " --top %d" % top["requested"]),
              "```", "",
              "And the way to make this page obsolete is to stop giving it aggregate scores. "
              "One table of trial, item, correct answers the questions in the second section, "
              "which are the ones that decide whether %s is worth running at all." % name, ""]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--table", type=Path, required=True,
                        help="a CSV of model,score -- a leaderboard, nothing more")
    # Taken as a string and validated in this file's voice rather than
    # argparse's: a reader told only "argument --items is required" will supply
    # a number they made up.
    parser.add_argument("--items", default=None,
                        help="how many items the benchmark has. Required; never assumed. "
                             "Without it there is no sampling error and no claim below it.")
    parser.add_argument("--scale", choices=("proportion", "percent"), default=None,
                        help="whether the score column is 0-1 or 0-100. Only needed when the "
                             "file is ambiguous, which is when nothing in it exceeds 1.0.")
    parser.add_argument("--top", type=int, default=TOP,
                        help="how many leading models the compression section is about "
                             "(default %d)" % TOP)
    parser.add_argument("--benchmark", help="what to call the benchmark in the closing line")
    parser.add_argument("--json", action="store_true",
                        help="print the record instead of the page")
    args = parser.parse_args(argv)

    items = required_items(args.items)
    if args.top < 2:
        raise SystemExit("--top was given %d; a group of fewer than two has no ordering in it "
                         "to support or refute." % args.top)
    rows, scale = read_leaderboard(args.table, args.scale)
    found = check(rows, items, args.top)
    found["source"] = str(args.table)
    found["scale"] = scale
    if args.json:
        print(json.dumps(found, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(render(found, str(args.table), scale, args.benchmark))


if __name__ == "__main__":
    main()
