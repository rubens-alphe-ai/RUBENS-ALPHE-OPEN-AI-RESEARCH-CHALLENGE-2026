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

And one optional section, off unless the buyer asks for it by naming their own
numbers. The page states the saving in items and in runs; `--cost-per-run` and
`--runs-per-year` restate it in money and in time. Nothing in it is measured.
Every figure is the buyer's own rate multiplied by a count this page has already
printed, and the page names which count — including the one it deliberately does
*not* use, because the saving is quoted on the items this page will actually
drop, never on the larger count of items that carry nothing.

  python scripts/instrument_report.py \\
      --report experiments/PUBLIC-AUDIT-2026-09/report-computer_security-top20.json \\
      --out report/ --instrument "MMLU computer_security" \\
      --population "the 20 highest-scoring models in HELM Lite v1.13.0" \\
      --cost-per-run 0.004 --runs-per-year 12 --currency EUR
"""

from __future__ import annotations

import argparse
import csv
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


# --------------------------------------------------------------------------
# Costing: the same saving, in the buyer's money and the buyer's hours.
#
# The page already says "removing 78 of these 83 items removes 70% of the
# runs". A buyer who signs cheques needs that in their own currency, and the
# two numbers that convert it are theirs: what one item-run costs them and how
# often they run the suite. So nothing below is measured, estimated or looked
# up. Every figure is a rate the buyer stated multiplied by a count this page
# has already printed, and the page prints the multiplication beside the
# result so it can be checked without trusting it.
#
# Three refusals, and they are the reason this is a class rather than two
# multiplications inline:
#
# * **The saving is quoted on the drop list, never on the count of items that
#   carry nothing.** Those are different numbers — 78 and 107 on the audit's
#   top-20 subset — because this page holds items back from deletion for
#   reasons it has just finished explaining. Costing all 107 as removable would
#   inflate the saving by a third using the very items the page refuses to
#   delete, which is the single easiest way for a costing to lie.
# * **A missing number is never filled in.** A cost per run with no
#   runs-per-year does not mean once a year. It means the buyer did not say, so
#   the run stops rather than invent a frequency for them.
# * **A rate that cannot be true is refused, not rounded.** Zero, negative,
#   non-numeric, nan, inf, a frequency below one run a year. Each exits naming
#   which flag and what was wrong with it.


def listed(parts: list[str]) -> str:
    """"a; b; and c" — semicolons because each part already has commas in it."""
    if not parts:
        return "none of them reached the drop list"
    if len(parts) == 1:
        return parts[0]
    return "%s; and %s" % ("; ".join(parts[:-1]), parts[-1])


def plain(value: float) -> str:
    """12 rather than 12.0, for a count the buyer typed as a whole number."""
    return str(int(value)) if float(value).is_integer() else ("%g" % value)


def money(amount: float, currency: str) -> str:
    """`EUR 5.33`, and `EUR 0.004` for a rate a cent would round away to nothing."""
    if 0 < abs(amount) < 0.01:
        text = format(amount, ",.6f").rstrip("0")
        return "%s %s" % (currency, text + "0" if text.endswith(".") else text)
    return "%s %s" % (currency, format(amount, ",.2f"))


def duration(seconds: float) -> str:
    """Item-run time in the largest unit that does not hide the size of it."""
    value, unit = ((seconds / 3600.0, "hours") if seconds >= 3600 else
                   (seconds / 60.0, "minutes") if seconds >= 60 else (seconds, "seconds"))
    text = format(value, ",.1f")
    return "%s %s" % (text[:-2] if text.endswith(".0") else text, unit)


def finite_number(raw: object, flag: str, what: str, example: str) -> float:
    """A number this page can multiply, or an exit naming the flag that was wrong.

    Written out rather than left to argparse's `type=float` so that a buyer who
    typed a price with a currency symbol in it is told what to do about it, in
    the voice of the rest of this file. ASCII only: this goes to stderr, and a
    Windows console that cannot encode an em dash turns a refusal into a
    traceback about the refusal.
    """
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        raise SystemExit("%s was given %r, which is not a number. Give %s as a plain decimal "
                         "with no currency symbol, thousands separator or unit, for example "
                         "%s %s." % (flag, raw, what, flag, example))
    if not math.isfinite(value):
        raise SystemExit("%s was given %r, which is not a finite number, so every figure "
                         "derived from it would be meaningless. Give %s as a plain decimal, "
                         "for example %s %s." % (flag, raw, what, flag, example))
    return value


def positive_number(raw: object, flag: str, what: str, example: str) -> float:
    """A rate above zero. Zero is refused rather than costed: a page that prices
    the runs at nothing reports every saving as free."""
    value = finite_number(raw, flag, what, example)
    if value <= 0:
        raise SystemExit("%s was given %s, and %s of zero or less would make this page report "
                         "a saving that is free or negative. If your runs genuinely cost you "
                         "nothing, leave the costing flags off: the page is complete without "
                         "them." % (flag, plain(value), what))
    return value


def read_cost_table(path: Path) -> dict[str, float]:
    """Per-item costs from a two-column table, so the equal-cost assumption can go.

    An item whose question and expected answer are long costs more to run than a
    short one, sometimes by an order of magnitude. Where the buyer can say so
    per item, the flat rate is not used at all and the page stops claiming the
    items cost the same.

    Columns named in a header row: an item identifier matching the one in the
    analysis, and a cost. Same shape and the same column-naming tolerance as
    `item_analysis.from_table`, because a harness that can emit one can emit
    this.
    """
    costs: dict[str, float] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or len(reader.fieldnames) < 2:
            raise SystemExit("%s needs a header row with an item column and a cost column" % path)
        names = {name.strip().lower(): name for name in reader.fieldnames}

        def column(*candidates: str) -> str:
            for candidate in candidates:
                if candidate in names:
                    return names[candidate]
            raise SystemExit("%s has no column named any of %s; found %s"
                             % (path, " / ".join(candidates), ", ".join(reader.fieldnames)))

        item_col = column("item", "item_id", "question", "question_id", "task", "id")
        cost_col = column("cost", "cost_per_run", "price", "amount", "spend", "unit_cost")
        for line in reader:
            item = str(line[item_col]).strip()
            value = positive_number(line[cost_col], "--cost-table",
                                    "the cost of item %r" % item, "0.004")
            if item in costs and costs[item] != value:
                raise SystemExit("%s gives item %r two different costs, %s and %s. One of them "
                                 "is wrong and this page will not pick which."
                                 % (path, item, plain(costs[item]), plain(value)))
            costs[item] = value
    if not costs:
        raise SystemExit("%s has a header row and no costs under it" % path)
    return costs


class Costing:
    """What the buyer said their runs cost. Held as an object so that no figure
    on the page can be produced without the rate and the frequency that made it,
    and so that the page can print the multiplication next to every result."""

    def __init__(self, runs_per_year: float, currency: str = "EUR",
                 cost_per_run: float | None = None,
                 cost_by_item: dict[str, float] | None = None,
                 cost_source: str | None = None,
                 seconds_per_run: float | None = None) -> None:
        self.runs_per_year = runs_per_year
        self.currency = currency
        self.cost_per_run = cost_per_run
        self.cost_by_item = cost_by_item
        self.cost_source = cost_source
        self.seconds_per_run = seconds_per_run

    @property
    def priced(self) -> bool:
        return self.cost_per_run is not None or self.cost_by_item is not None

    @property
    def timed(self) -> bool:
        return self.seconds_per_run is not None

    @property
    def flat(self) -> bool:
        """True when one rate is being applied to every item — the assumption
        the page has to state out loud, because it is usually false."""
        return self.cost_per_run is not None

    @classmethod
    def declared(cls, cost_per_run: object = None, runs_per_year: object = None,
                 currency: object = "EUR", cost_table: Path | None = None,
                 seconds_per_run: object = None) -> "Costing | None":
        """Validate what the buyer typed, or refuse. None when they asked for no
        costing at all, which is the default and leaves the page untouched."""
        asked = [name for name, given in (("--cost-per-run", cost_per_run is not None),
                                          ("--cost-table", cost_table is not None),
                                          ("--seconds-per-run", seconds_per_run is not None),
                                          ("--runs-per-year", runs_per_year is not None))
                 if given]
        if not asked:
            return None
        if cost_per_run is not None and cost_table is not None:
            raise SystemExit("--cost-per-run and --cost-table both say what an item-run costs, "
                             "and they disagree by construction. Give one: --cost-table when "
                             "your items cost different amounts, --cost-per-run when one rate "
                             "covers them all.")
        if runs_per_year is None:
            raise SystemExit("%s needs --runs-per-year beside it: a cost per run is not a cost "
                             "per year until someone says how often the suite is run. This page "
                             "will not assume a frequency you did not state."
                             % " and ".join(asked))
        if cost_per_run is None and cost_table is None and seconds_per_run is None:
            raise SystemExit("--runs-per-year on its own says how often you run the suite but "
                             "not what a run costs you. Add --cost-per-run (or --cost-table) "
                             "for money, --seconds-per-run for time, or leave all of them off.")

        runs = finite_number(runs_per_year, "--runs-per-year",
                             "the number of times a year the whole suite is run", "12")
        if runs < 1:
            raise SystemExit("--runs-per-year was given %s. A suite run less than once a year "
                             "has no annual cost to save, and scaling one year's figures by a "
                             "fraction of a run would report a saving nobody banks. State how "
                             "many times a year the whole suite runs, at least 1." % plain(runs))
        name = str(currency if currency is not None else "").strip()
        if not name:
            raise SystemExit("--currency was given an empty value. Every money figure on this "
                             "page is printed with its unit; leave the flag off to use EUR.")

        rate = None if cost_per_run is None else positive_number(
            cost_per_run, "--cost-per-run", "the money one item-run costs you", "0.004")
        by_item = None if cost_table is None else read_cost_table(cost_table)
        seconds = None if seconds_per_run is None else positive_number(
            seconds_per_run, "--seconds-per-run", "the time one item-run takes", "12")
        return cls(runs_per_year=runs, currency=name, cost_per_run=rate, cost_by_item=by_item,
                   cost_source=None if cost_table is None else str(cost_table),
                   seconds_per_run=seconds)

    def covering(self, per_item: list[dict]) -> None:
        """Refuse a cost table that does not price every item being counted.

        A missing item cannot be priced at zero — that understates the suite and
        overstates the share the drop list saves — and it cannot be priced at
        the average, because there is no rate here to average.
        """
        if self.cost_by_item is None:
            return
        missing = [row["item"] for row in per_item if row["item"] not in self.cost_by_item]
        if missing:
            raise SystemExit("%s prices %d items, but the analysis counts %d and %s %s no cost "
                             "in it. Every counted item needs a cost: filling a zero would "
                             "understate what the suite costs you and overstate the share that "
                             "dropping items gives back."
                             % (self.cost_source, len(self.cost_by_item), len(per_item),
                                naming([{"item": name} for name in missing]),
                                "have" if len(missing) > 1 else "has"))

    def annual_money(self, rows: list[dict]) -> float | None:
        if not self.priced:
            return None
        if self.cost_by_item is not None:
            per_pass = sum(self.cost_by_item[row["item"]] for row in rows)
        else:
            per_pass = self.cost_per_run * len(rows)
        return per_pass * self.runs_per_year

    def annual_seconds(self, rows: list[dict]) -> float | None:
        if not self.timed:
            return None
        return self.seconds_per_run * len(rows) * self.runs_per_year

    def money_working(self, rows: list[dict]) -> str:
        """The multiplication, so the number can be checked rather than believed."""
        if self.cost_by_item is not None:
            return ("the %d per-item costs you gave, added up, times %s runs a year"
                    % (len(rows), plain(self.runs_per_year)))
        return ("%d items x %s an item-run x %s runs a year"
                % (len(rows), money(self.cost_per_run, self.currency), plain(self.runs_per_year)))

    def time_working(self, rows: list[dict]) -> str:
        return ("%d items x %s an item-run x %s runs a year"
                % (len(rows), duration(self.seconds_per_run), plain(self.runs_per_year)))


def costing_section(costing: Costing, per_item: list[dict], carrying_items: list[str],
                    droppable: list[dict], held_measuring: list[dict],
                    held_backwards: list[dict]) -> list[str]:
    """The money and the time, each tied to a count printed elsewhere on the page.

    Three quantities, in the order a buyer reads them: what the whole suite
    costs, what the part of it that carries nothing costs, and what can actually
    be saved today. The third is smaller than the second and the paragraph after
    them says why, because that gap is where a costing like this would otherwise
    quietly overstate itself.
    """
    counted = len(per_item)
    carrying = set(carrying_items)
    dead = [row for row in per_item if row["item"] not in carrying]
    held = len(held_measuring) + len(held_backwards)

    lines = ["## What this costs you, in money and in hours", "",
             "These are your numbers, not measurements. This page multiplies the rate you gave "
             "by counts it has already printed above; it did not observe what anything costs "
             "you.", ""]

    if costing.priced:
        lines += ["- **Running all %d items costs %s a year** — %s."
                  % (counted, money(costing.annual_money(per_item), costing.currency),
                     costing.money_working(per_item)),
                  "- **The %d items that carry nothing cost %s of that** — %s."
                  % (len(dead), money(costing.annual_money(dead), costing.currency),
                     costing.money_working(dead))]
        if droppable:
            saving = costing.annual_money(droppable)
            whole = costing.annual_money(per_item)
            share = 100.0 * saving / whole if whole else 0.0
            lines.append("- **Dropping the %d items this page puts on the drop list saves %s a "
                         "year**, %.0f%% of what the suite costs you — %s."
                         % (len(droppable), money(saving, costing.currency), share,
                            costing.money_working(droppable)))
        else:
            lines.append("- **Nothing on this page can be dropped, so the saving available "
                         "today is %s.** No item reached the drop list above, and this page "
                         "will not cost an item as removable that it has not recommended "
                         "removing." % money(0.0, costing.currency))
    if costing.timed:
        lines += ["- **Running all %d items takes %s of item-run time a year** — %s."
                  % (counted, duration(costing.annual_seconds(per_item)),
                     costing.time_working(per_item))]
        if droppable:
            lines.append("- **Dropping the %d items on the drop list gives back %s of that a "
                         "year** — %s."
                         % (len(droppable), duration(costing.annual_seconds(droppable)),
                            costing.time_working(droppable)))
        lines.append("  That is item-run time added up, not time on a clock. Runs that happen "
                     "side by side finish sooner than this and the total spent is the same.")
    lines.append("")

    # The gap between "carries nothing" and "can be removed" is where a costing
    # like this would overstate itself, so the page accounts for every item in
    # it rather than for the ones with the tidiest explanation.
    if len(dead) > len(droppable):
        reasons = []
        if held_measuring:
            reasons.append("%d still %s respondents despite being answered the same way by "
                           "almost everyone"
                           % (len(held_measuring),
                              "separate" if len(held_measuring) > 1 else "separates"))
        if held_backwards:
            reasons.append("%d %s waiting on the key check above, and a key cannot be checked "
                           "after the item has been deleted"
                           % (len(held_backwards), "are" if len(held_backwards) > 1 else "is"))
        rest = len(dead) - len(droppable) - held
        if rest:
            reasons.append("%d do vary between respondents rather than being answered alike, so "
                           "this page has not put %s on a deletion list at all"
                           % (rest, "them" if rest > 1 else "it"))
        lines += ["The saving is counted on the %d items on the drop list, not on all %d that "
                  "carry nothing. Of the other %d: %s. Costing any of them as removable would "
                  "put money on this page that the page has just declined to recommend you save."
                  % (len(droppable), len(dead), len(dead) - len(droppable),
                     listed(reasons)), ""]

    if costing.flat:
        lines += ["**This arithmetic assumes every item costs you the same to run.** That is "
                  "usually false. A question with a long stem and a long expected answer costs "
                  "several times what a short one costs, so if the items on the drop list are "
                  "the short ones you will save less than the figure above, and if they are the "
                  "long ones you will save more. Where you know the per-item cost, pass "
                  "`--cost-table` with a cost for each item and this page will use yours "
                  "instead of assuming.", ""]
    else:
        lines += ["These figures do not assume the items cost the same: each one is priced from "
                  "the per-item costs you supplied in `%s`, so an item that costs more to run "
                  "is worth more when it is dropped." % str(costing.cost_source).replace("\\", "/"),
                  ""]

    lines += ["It also assumes the only thing that goes away is the per-item cost you named. "
              "Setting up the harness, reviewing the output and anything billed per run of the "
              "whole suite rather than per item are unchanged by dropping items, and none of "
              "them are in the figures above.", "",
              "And it is a saving on this population. The drop list is what these respondents "
              "made constant; a wider or narrower field would make a different set of items "
              "constant, so re-run the analysis before banking the same number next year.", ""]
    return lines


def render(report: dict, instrument: str | None = None, population: str | None = None,
           costing: Costing | None = None) -> str:
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

    if costing is not None:
        costing.covering(per_item)
        # The set the short version calls "counted in the score and carry
        # nothing" — taken from the record's own list so the costing cannot
        # drift from the count printed at the top of the page.
        carrying_items = length.get("carrying_items")
        if carrying_items is None:
            carrying_items = [row["item"] for row in per_item
                              if row.get("discrimination") is not None
                              and row["discrimination"] >= ia.WEAK
                              and ia.FLOOR < row["difficulty"] < ia.CEILING]
        lines += costing_section(costing, per_item, carrying_items, droppable,
                                 held_measuring, held_backwards)

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
    # Optional, and off by default: without them the page is exactly what it was
    # before this costing existed. Taken as strings rather than floats so that a
    # bad value is refused by this file, in this file's voice, instead of by
    # argparse's.
    parser.add_argument("--cost-per-run", help="what one item-run costs you, as a plain "
                                               "decimal. Needs --runs-per-year beside it.")
    parser.add_argument("--cost-table", type=Path,
                        help="a CSV of item,cost giving what each item costs you, for when the "
                             "items do not cost the same. Use instead of --cost-per-run.")
    parser.add_argument("--runs-per-year", help="how many times a year the whole suite is run. "
                                                "At least 1; never assumed.")
    parser.add_argument("--seconds-per-run", help="how long one item-run takes, for the saving "
                                                  "in hours as well as in money")
    parser.add_argument("--currency", default="EUR",
                        help="the unit every money figure is printed with (default EUR). This "
                             "page converts nothing; it prints your rate in your unit.")
    args = parser.parse_args()

    costing = Costing.declared(cost_per_run=args.cost_per_run, runs_per_year=args.runs_per_year,
                               currency=args.currency, cost_table=args.cost_table,
                               seconds_per_run=args.seconds_per_run)
    text = sys.stdin.read() if str(args.report) == "-" else args.report.read_text(encoding="utf-8")
    report = json.loads(text)
    page = render(report, args.instrument, args.population, costing)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "REPORT.md").write_text(page, encoding="utf-8")
    summary = {"out": str(args.out / "REPORT.md"),
               "reading": report["effective_length"]["reading"],
               "items_running_backwards": len(negative_items(report["per_item"])),
               "population_named": bool(args.population)}
    if costing is not None and costing.priced:
        droppable, _measuring, _backwards = to_drop(report["per_item"])
        summary["annual_saving"] = {
            "currency": costing.currency,
            "items_dropped": len(droppable),
            "amount": round(costing.annual_money(droppable), 4)}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
