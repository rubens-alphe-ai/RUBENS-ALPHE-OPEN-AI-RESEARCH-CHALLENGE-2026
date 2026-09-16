# ADR-004: Decision rules must be able to reach a verdict

**Status:** Accepted
**Date:** 2026-09-16
**Deciders:** Mission Rubens project owner (delegated: "fais la meilleure solution")

## Context

After MEM-002, two rules of the V4 adjudicator were examined against the data
they will meet in a larger experiment.

**Fabrication.** V4 rejects the candidate as soon as one critical fabrication
is confirmed in *any* answer, baseline included. MEM-002 was rejected on one
fabrication in each condition. The rule therefore punishes the candidate for
errors the control made at the same rate. The PCRB-1 rubric states a different
rule: structured memory is acceptable only if the fabrication count "does not
increase". With 60 answers from any current model, at least one confirmed
fabrication somewhere is close to certain, so V4 fixes the verdict before the
experiment runs.

**Evaluator disagreement.** V4 makes the whole experiment inconclusive if two
scorers differ by more than 15 points on a single answer. MEM-002 already had
such an answer (100 against 80). With 30 pairs, one such answer is close to
certain, and the rule again fixes the verdict in advance.

A rule whose outcome is known before the data exists is not a test.

## Decision

Two options are added to the adjudicator's `evidence_policy`. Their defaults
reproduce V4 exactly, so MEM-001 and MEM-002 keep the verdicts they were
frozen with.

1. `fabrication_rule`
   - `"any"` (default, V4): any confirmed fabrication rejects.
   - `"comparative"`: every report must still be resolved by the majority
     rule; then the candidate is rejected when the structured condition has
     **more** confirmed fabrications than baseline. Counts per condition are
     always reported.
2. `max_disagreeing_pair_fraction`
   - `0` (default, V4): one disagreeing pair makes the experiment inconclusive.
   - above 0: disagreeing pairs stay in the analysis with the mean of their
     scores, are listed by name, and the experiment is inconclusive only if
     their share exceeds the value.

The options are only valid when committed in the experiment's
`evaluation_policy.json` **before its trials run**. Choosing them after seeing
data would be exactly the post-hoc adjustment the gate exists to prevent.

The other V4 thresholds are unchanged: mean paired improvement of at least 10
points, lower 95 % bound above 5, and no `FINAL_KEEP` without replication,
holdout, calibration and regression evidence.

## Consequences

- Experiments from MEM-003 on can reach KEEP or REJECT on the question they
  ask, instead of on the base rate of model errors.
- A candidate that fabricates as often as the control is no longer rejected
  for it. A reader who wants zero fabrication must look at the per-condition
  counts, which every decision now reports.
- MEM-002 is not re-adjudicated under the new rules. A sensitivity analysis may
  be reported, labelled as such; it does not replace the recorded verdict.
