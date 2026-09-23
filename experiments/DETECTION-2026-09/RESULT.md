# How often the audit is right

Every number this project has published about a benchmark was a claim about
data whose truth nobody knew. This one is different: the defects were planted,
so the answer is known before the tool runs, and the tool's accuracy can be
stated rather than assumed.

Reproduce with:

    python scripts/detection_rate.py --replications 500

Stored output: [`detection-report.json`](detection-report.json). Seed 20260922,
500 replications per sample size, 20 healthy items and 3 of each defect per
dataset, thresholds taken unchanged from `scripts/item_analysis.py`.

## Two lists, not one

The first version of this compared each estimate against a fixed threshold. An
estimate from twenty respondents is poor, and treating it as exact is what
produced a false alarm on roughly one healthy item in seven.

The fix is to compare the **interval** around the estimate against the
threshold, so a flag fires only where a healthy item could not plausibly have
produced the data. That does not come free, and the size of the trade is the
most useful thing on this page:

| Respondents | | Mis-keyed found | Noise found | **Healthy falsely flagged** |
| --- | --- | --- | --- | --- |
| 20 | screening | 0.976 | 0.797 | **0.144** |
| | asserting | 0.500 | 0.124 | **0.002** |
| 50 | screening | 0.999 | 0.919 | 0.051 |
| | **asserting** | **0.880** | 0.289 | **0.000** |
| 100 | screening | 1.000 | 0.974 | 0.015 |
| | **asserting** | **0.988** | 0.483 | **0.000** |
| 200 | screening | 1.000 | 0.997 | 0.003 |
| | **asserting** | **1.000** | 0.787 | **0.000** |

So the tool now produces two lists from one analysis, and they answer different
questions:

- **The screening list** (`flags`) — *what is worth looking at*. It misses
  almost nothing and over-accuses. Right for a human who is going to check.
- **The asserting list** (`flags_confident`) — *what the data will support in
  writing*. Right for a report, a deletion decision, or anything a customer
  acts on without looking.

`flags` is unchanged from what was published, and a test pins that the
asserting list is always a subset of it. The two can never disagree about an
item; one is simply more cautious.

**At fifty respondents and above, the asserting list is the product.** 88% of
mis-keyed items found and no false alarm survived 500 replications. Below
fifty, neither setting is good: screening over-accuses at 14%, asserting finds
only half. Say so rather than choosing one.

Noise items — questions unrelated to what the rest measures — remain the
hardest call, still under 0.8 at two hundred respondents on the asserting list.
That threshold sits close to ordinary sampling noise, and no amount of care
about intervals moves it much.

Dead-item detection is unchanged by this: a difficulty interval that clears the
ceiling is a stricter test, and the rates above the fold still hold.

**Detection is never reported without false alarms**, in the tool and here. A
tool that flags every item detects every defect, and a tool that flags nothing
never raises a false alarm. Neither rate means anything alone, and the output
is shaped so that quoting one in isolation takes deliberate effort.

## What this licenses us to say

**The mis-keyed claim holds.** An item scored against the wrong answer is found
97.6% of the time with twenty respondents and essentially always with fifty.
This is the claim the product is sold on, and it is the strongest of the three.

**Below fifty respondents, one healthy item in seven is flagged.** That is the
honest limit, and it is not small. On a panel of twenty models, a report naming
ten suspect items is naming roughly one and a half that are fine. Any audit run
at that size must say so in the report, beside the list, not in a footnote.

**The effective length is understated, never overstated.** At twenty
respondents the tool says a test measures with about two fewer items than it
does. Which direction the error runs decides what it costs: understating loses
the buyer items they could have kept, while overstating would leave dead items
in the test and tell them their instrument is healthier than it is. We make the
error that is recoverable.

## What is odd, and why

Dead-item detection does not improve monotonically: 0.944 at twenty
respondents, 0.923 at fifty, then up. This is not noise and not a bug. A dead
item here is passed with probability 0.98, and the ceiling rule fires at a
difficulty of 0.95 or above. At twenty respondents that allows one failure; at
fifty it allows two, against an expected one. The gap between the threshold and
the expected number of failures closes and reopens as the sample grows, because
a count is discrete and a threshold is not. It is a property of any fixed
cutoff, it is visible only because the truth is known here, and it is the sort
of thing that would otherwise be discovered by a customer.

## The limit of this result, stated plainly

Responses were generated from a two-parameter logistic: one ability per
respondent from a standard normal, one difficulty and one discrimination per
item, outcomes drawn independently.

**Real benchmarks are not that.** Items there share topics, respondents share
training data, and neither the independence assumption nor the single-ability
assumption survives contact with a real leaderboard. Every rate above is
therefore an **upper bound on detection and a lower bound on false alarms**. A
real dataset can only be harder than this one.

That sentence travels inside the JSON output, not only in this file, because an
upper bound separated from its condition is how a bound becomes quoted as a
guarantee.

## The operating rules this produces

**Fifty respondents is the line.** At or above it, report the asserting list
and state nothing else as a finding: 88% to 100% of mis-keyed items, no false
alarm in 500 replications.

**Below fifty, publish both lists and label them.** The screening list still
finds what is broken and still accuses about one healthy item in seven; the
asserting list at that size finds only half. Neither is a verdict on its own,
and a buyer who deletes from the screening list loses items they needed.

**Never quote a detection rate without the false alarm rate beside it.** The
table above is the reason: moving from one list to the other trades 48 points
of detection for 14 points of false alarm at twenty respondents. Either number
alone would recommend the opposite choice.
