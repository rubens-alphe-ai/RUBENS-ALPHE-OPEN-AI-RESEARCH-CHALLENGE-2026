# What these tools refuse to tell you

Every vendor shows what their tool outputs. This page is the other list: what
it declines to output, and why each refusal is worth more than the number it
withholds.

A measuring instrument that answers every question asked of it is not
measuring. It is generating. The difference shows up only in the cases where
the honest answer is *not enough information*, and those are exactly the cases
where a plausible number does the most damage — because a plausible number
gets acted on.

Each entry names the file that holds it. All of them are enforced in code and
covered by tests, not guidance in a manual.

## It refuses data it cannot read correctly

**A graded score is refused, not rounded.**
`item_analysis.py` handles right-or-wrong records. Given a 1-to-5 rubric it
does not threshold it — it stops and names `graded_items.py`, which takes the
scale range. We know what the other behaviour costs, because we shipped it:
see [defect 4](CAUGHT_IN_OUR_OWN_WORK.md).

**A scale with no range is refused.**
`graded_items.py` will not accept a low equal to its high, and refuses a
two-point "scale" as *a binary item wearing a range* — that data belongs in the
other tool, scored the other way.

**A score outside the declared scale is refused**, naming the item and the
trial, rather than being clamped to the nearest end.

**A trial that did not answer every item is dropped, not scored zero.**
Filling a zero converts an absent answer into a wrong one, which is the
difference between a gap in the data and a failure by the respondent.

**A table whose columns cannot be identified is refused** with the names it
looked for and the names it found, rather than guessing at column order.

## It refuses numbers the data cannot support

**A threshold is put against the interval, not against the estimate.**
A discrimination from twenty respondents is a poor estimate, and comparing it
to a fixed cutoff as though it were exact accused roughly one healthy item in
seven. The tool now produces two lists: what is worth looking at, and what the
data will support in writing. Which one applies depends on how many
respondents there are, and
[the characterisation](../experiments/DETECTION-2026-09/RESULT.md) says where
the line falls rather than leaving it to taste.

**Alpha is undefined rather than zero when nothing varies.**
A reliability of 0.0 says *this test is unreliable*. Undefined says *this data
cannot tell you*. They are different statements and only one of them is true
when every respondent scores alike.

**Fewer than three trials gets no item statistics at all.** A difficulty from
two respondents is a fraction, not a difficulty.

**A detection rate from too few replications is refused.** The characterisation
tool will not print a rate to three digits from a handful of runs, because
those digits would not be there. Thirty replications is the floor.

**Item response theory answers "the question cannot be answered at this size"**
when it applies. On the restricted MMLU panel, injecting an enormous parameter
drift produced a result indistinguishable from no drift at all — the test had
no power, so agreement and disagreement were both consistent with noise. That
verdict is carried in the output as `answerable: false`, and the statistics
below it are marked as not being an answer.

**A factor resting on one respondent is flagged as such.** Parallel analysis
retained three dimensions in our own quiz; two of them turned out to be a
single reader, so the tool now prints how many trials sit on a factor's
minority side. The method was right to retain them and nobody should believe
them.

## It refuses to report a rate in a form that misleads

**Detection is never printed without false alarms.** A tool that flags every
item detects every defect; one that flags nothing never raises a false alarm.
The output is structured so that quoting either alone takes deliberate effort.

**The generating model and its limit travel inside the data file**, not only in
the prose beside it. The rates hold for synthetic data of one shape, they are
an upper bound on real data, and that sentence is in the JSON — because a bound
separated from its condition becomes quoted as a guarantee.

**The thresholds used are the shipped ones**, and a test pins that they were
not tuned for the characterisation. Rates measured against adjusted cutoffs
would describe a tool nobody is sold.

## It refuses to make an unmeasured thing look measured

**An unavailable field reports `unmeasured`, never `0` and never `ok`.**
Zero completed external replications is not a score of zero; it is an absence
of evidence, and `status_tuple.py` says so in that word.

**There is deliberately no overall score.** Five fields, no average. An average
would let a strong field hide a missing one, which is the whole failure mode
the status record exists to prevent.

**A run whose failures fall unevenly across conditions is marked
`UNUSABLE — do not analyse the tables below`**, as the first line of its own
report. Not "interpret with caution". The tables are still printed, and the
instruction not to read them comes first.

**A threshold that cannot be reached is caught before the data arrives.**
`check_headroom.py` refuses a target the control's own prior makes impossible —
including the case where the confidence-interval clause binds harder than the
threshold itself. Two pre-registered thresholds in this project were impossible
when written, and neither was noticed until this check existed.

## It refuses to let the free check pass for the paid one

`leaderboard_check.py` reads only what is already public — model names and
their scores — so that a stranger can get an alarming, honest number without
extracting anything. Most of what it does is decline.

**It will not run without being told how many items the test has.** Without
that count there is no sampling error, and every claim it makes is built on
one. It refuses in its own words rather than argparse's, because a reader told
"argument required" invents a number.

**It refuses to guess whether a score is a proportion or a percentage.** A
board sitting entirely at or below 1.0 could be either, and the two readings
differ by a factor of a hundred in the only quantity the tool computes. That is
not a rounding, it is the whole answer, so it names both readings and stops.

**It says in its own second section that it is not the audit.** Mis-keyed
items, dead items and effective length each get named, with why an aggregate
score cannot see them and what input can. Those three travel in the JSON record
as well, so a caller cannot print the findings without them.

**It refuses to convict a benchmark for clustering.** Models bunched at the top
may simply be that close, and that possibility is listed first. Telling them
apart needs per-item data, which the page says it does not offer.

**It reports its errors in both directions.** Correlated items make the true
error larger, so every tie it finds is an undercount; and because it compares
models without pairing, every tie is also conservative against itself. The
correct paired test needs the per-item table — which is the cleanest place the
free check visibly stops.

**It declines to cry wolf.** Where models are genuinely far apart it says so
and writes a deliberately narrow clean bill, and a test pins that the alarmed
wording is absent.

## It refuses to price what it has not counted

**A cost of zero or less is refused** rather than producing a saving of
infinity or of nothing.

**A cost per run without a runs-per-year is refused**: a cost per run is not a
cost per year, and supplying the missing number ourselves would be inventing
the buyer's usage.

**An item priced twice with two different figures is refused**, naming both.

**A price list covering a different set of items than the analysis counted is
refused**, rather than quietly costing the overlap and reporting a total that
looks complete.

---

**Why publish this.** Because the refusals are the part that took the longest
and that a reimplementation will not have. The statistics here are a century
old and public; anyone can rebuild them in a weekend. What cannot be rebuilt in
a weekend is the list of cases where the obvious behaviour is wrong — and that
list was assembled the expensive way, by shipping several of them first.
