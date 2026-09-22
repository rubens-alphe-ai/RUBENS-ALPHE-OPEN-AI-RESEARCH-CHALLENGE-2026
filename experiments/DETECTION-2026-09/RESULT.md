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

## The two rates

| Respondents | Mis-keyed found | Dead found | Noise found | **Healthy items falsely flagged** | Effective length error |
| --- | --- | --- | --- | --- | --- |
| 20 | 0.976 | 0.944 | 0.797 | **0.144** | −2.22 items |
| 50 | 0.999 | 0.923 | 0.919 | 0.051 | −0.74 |
| 100 | 1.000 | 0.985 | 0.974 | 0.015 | −0.22 |
| 200 | 1.000 | 0.999 | 0.997 | 0.003 | −0.04 |

95% interval on the two numbers that matter most, at 20 respondents:
mis-keyed detection [0.967, 0.983], false alarm [0.137, 0.151].

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

## The operating rule this produces

Do not sell an audit on fewer than fifty respondents without stating the false
alarm rate in the report itself. At twenty the tool still finds what is broken;
it also accuses roughly one healthy item in seven, and a buyer who deletes on
that basis loses items they needed.
