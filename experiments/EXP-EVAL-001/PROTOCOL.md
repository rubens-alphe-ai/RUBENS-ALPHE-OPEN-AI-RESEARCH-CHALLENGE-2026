# EXP-EVAL-001 — Independent Evaluator Reliability Test

## Goal

Measure whether independent evaluator models can score identical blinded
outputs consistently enough for a future automated gate.

## Protocol

1. Freeze a calibration packet containing outputs from both conditions and a
   small holdout packet that evaluators never see during calibration.
2. Remove condition labels, expected scores and previous evaluator answers.
3. Send the exact same packet to at least two evaluator providers/models.
4. Require one machine-readable scorecard per output with all PCRB-1 component
   scores, total, fabrication objects and provenance hashes.
5. Pair cards by output hash and compare total scores inside each output, not
   across unrelated outputs.
6. Record disagreement, calibration pass/fail and the holdout result.

## Gate

- Fewer than two independent evaluators: `INCONCLUSIVE`.
- A disagreement above 15 points on any paired output: `INCONCLUSIVE`.
- One fabrication report without independent confirmation: `INCONCLUSIVE`.
- Two independent fabrication reports on the same output: `REJECT`.
- The evaluator gate is not allowed to adopt canonical state by itself.

This protocol is registered but not yet executed.
