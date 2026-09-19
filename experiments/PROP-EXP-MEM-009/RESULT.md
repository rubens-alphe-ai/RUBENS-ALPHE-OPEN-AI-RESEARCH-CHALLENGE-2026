# PROP-EXP-MEM-009 — Result: the population hypothesis, refused as registered

**Stage 1 of the Continuity Programme fails its own rule.** Merging several
independent chains does **not** recover 15 points over their mean at equal
length. The measured recovery is +11.6, +6.9 and +1.4 points, and **no merge on
any document beat the best single chain it came from.**

The refutation is recorded as the programme required, and it is more precise
than the hypothesis it replaces.

## What was run

The six chains of the `summary` strategy from MEM-008 were taken at hop 5, for
each of the three documents. A model that never saw the document — and never
saw the quiz — merged all six end points into one handoff under the same 150-word
budget. Six independent merges per document, each read and graded like any other
handoff.

| Document | Sources (mean) | Best single chain | Merge at 150 words | vs mean | vs best |
|---|---|---|---|---|---|
| Clinic | 61.6 % | 73.9 % | 73.2 % | +11.6 | −0.7 |
| Observatory | 70.1 % | 79.2 % | 77.1 % | +6.9 | −2.1 |
| Vineyard | 79.9 % | 83.3 % | 81.2 % | +1.4 | −2.1 |

Zero invented facts in every merge, on every document. The merger reconciled
six diverging notes without adding anything — the failure mode the rule was
written to catch did not occur.

**At a fixed budget, merging recovers dispersion, not loss.** It reaches the
level of the best witness and stops there.

## The follow-up, exploratory: widen the channel

The pattern suggested the constraint was bandwidth, not redundancy: six notes
cannot fit into the budget of one. The same merges were rerun with 300 words
instead of 150. **This was decided after seeing the first result and is
therefore exploratory, not part of any registered rule.**

| Document | Sources (mean) | Best single | Merge 150 | Merge 300 | 300 vs best single |
|---|---|---|---|---|---|
| Clinic | 61.6 % | 73.9 % | 73.2 % | **80.4 %** | **+6.5** |
| Observatory | 70.1 % | 79.2 % | 77.1 % | **81.9 %** | **+2.8** |
| Vineyard | 79.9 % | 83.3 % | 81.2 % | 79.2 % | −4.2 |

With room to write, merging exceeds the best single chain on two documents of
three. On the third it does not, and that document is the one whose chains had
almost nothing to reconcile: its sources averaged 79.9 % with a best of 83.3 %,
a spread of 3.4 points against 12.3 for the clinic.

## What this supports, stated as a testable claim

> A population of handoffs repairs a project only to the extent that its members
> lost **different** things, and only if the channel that carries the merge is
> wider than the one that carried each source.

Both conditions are necessary. Diversity without bandwidth gains nothing;
bandwidth without diversity gains nothing.

This is not established: it comes from an exploratory run on three documents
with one merger model. It is registered here as the hypothesis for the next
experiment, which will fix its threshold before running: merge quality as a
function of source dispersion and budget ratio.

## Limits

- Six chains from one strategy, one writer family, one merger model.
- Dispersion was observed, not manipulated: a proper test varies it on purpose.
- The 300-word merges use more of the reader's attention as well as more words;
  a longer handoff is not only more informative, it is also a different reading
  task.
- The holdout stays sealed.
