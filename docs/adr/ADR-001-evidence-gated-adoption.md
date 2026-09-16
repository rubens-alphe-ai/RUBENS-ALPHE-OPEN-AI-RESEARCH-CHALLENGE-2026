# ADR-001: Evidence-gated candidate adoption

**Status:** Accepted for the RA-PSI evaluation pipeline  
**Date:** 2026-09-15  
**Deciders:** Mission Rubens project owner and peer-agent review

## Context

RA-PSI needs to improve across model changes without confusing a persuasive
answer with evidence. The current structured-memory result (85 baseline versus
100 structured) is a one-pair pilot and cannot by itself justify a canonical
state change. The peer-agent review also identified self-scoring bias, leakage,
benchmark overfitting, evaluator disagreement and rollback ambiguity.

## Decision

Use a provider-neutral, evidence-gated pipeline:

1. freeze protocol, prompt, state and raw-output hashes;
2. generate paired baseline/structured trials with fresh sessions;
3. blind the evaluator packet and keep the condition map private;
4. require independent scorecards and adjudicate disagreement inside each pair;
5. run calibration, rotating holdout and multi-capability regression checks;
6. classify evidence as `PROVISIONAL_KEEP`, `FINAL_KEEP`, `REJECT` or
   `INCONCLUSIVE`;
7. permit canonical adoption only for `FINAL_KEEP` through a separately
   guarded state-delta command.

## Options considered

### Option A: Proposer writes canonical state directly

| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Reproducibility | Low |
| Bias resistance | Poor |
| Rollback safety | Poor |

This is rejected because the proposer can certify its own output and can hide
regressions or uncertainty.

### Option B: Evidence-gated candidate delta (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Medium |
| Reproducibility | High |
| Bias resistance | Higher, subject to evaluator diversity |
| Rollback safety | High when hashes match |

The additional artifacts and test runs cost time, but they preserve raw
failures and make the adoption decision inspectable.

## Gate rules

- Pair by `pair_id` and evaluator, never by unrelated condition averages.
- Three paired trials are pilot evidence only.
- One critical-fabrication report is `INCONCLUSIVE`; two independent reports
  on the same output are `REJECT`.
- Disagreement above 15 PCRB-1 points within a paired output is
  `INCONCLUSIVE`.
- Final adoption requires at least nine paired trials, two generation model
  identities, evaluator diversity, holdout, calibration and regression pass.
- Rejection discards the candidate delta; it does not silently rewrite an
  already-adopted canonical state.

## Consequences

- Future models can replace the local adapter without changing the experiment
  or evaluator contract.
- The mailbox, local folder and public repository can carry the same hashes and
  recovery records.
- A promising result may remain provisional for longer, which is intentional.
- A human or authorized operator still needs to review and explicitly apply a
  final state delta.

## Implemented artifacts

- `schemas/evaluator-contract-v4.schema.json`
- `schemas/evaluator-scorecard.schema.json`
- `schemas/model-adapter.schema.json`
- `schemas/state-delta.schema.json`
- `scripts/build_blind_packets.py`
- `scripts/create_holdout_manifest.py`
- `scripts/adjudicate_evaluations.py`
- `scripts/apply_state_delta.py`
- `.github/workflows/evaluation-gate.yml`

## Action items

1. [x] Register the memory, evaluator-reliability and regression experiments.
2. [x] Add paired manifest and blind-packet tooling.
3. [x] Add deterministic adjudication tests and CI validation.
4. [x] Execute six fresh pilot trials.
5. [ ] Collect independent scorecards and run the pilot gate.
6. [ ] Replicate across the registered final evidence policy before adoption.
