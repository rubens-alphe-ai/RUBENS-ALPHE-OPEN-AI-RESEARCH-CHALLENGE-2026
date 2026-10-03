# Do our flags find the errors human experts found? — pre-registration

Written 2026-10-03, before the two sources below have been joined or compared.
Nothing in this file is edited after the result is computed.

## Why this matters

Every accuracy figure this project gives for its item flags comes from synthetic
data whose defects were planted by us (`experiments/DETECTION-2026-09`). Those
figures are an upper bound, and the result says so. This study tests the flags
on **real items judged by people**, which is the evidence the synthetic
characterisation cannot give.

## Data

- **Our flags.** The item analysis of HELM MMLU in `experiments/SURVEY-2026-09`:
  for each MMLU subject the survey audited, per-item discrimination and both
  flag lists, computed on up to sixty models (the first sixty in HELM's
  manifest order — not a random or strongest panel). No item analysis is
  re-run for this study.
- **Expert labels.** MMLU-Redux 2.0 (Gema et al., Edinburgh), 100 questions per
  subject re-annotated by experts, published under CC BY 4.0 at
  `huggingface.co/datasets/edinburgh-dawg/mmlu-redux-2.0`, read through the
  Hugging Face datasets server.
- **The join.** HELM instance text, from the `instances.json` named in each
  survey provenance manifest, matched to Redux questions by normalised question
  text (lower case, whitespace collapsed, punctuation removed). A Redux question
  matching no instance, or more than one, is dropped and counted.

## Definitions, fixed now

- **Key error** — Redux `error_type` = `wrong_groundtruth`.
- **Any error** — Redux `error_type` other than `ok`.
- **Screening flag** — the item's discrimination is below zero.
- **Strict flag** — the item carries a `negative` flag in `flags_confident`
  (the interval rule).
- **Enrichment** — the rate of key errors among flagged items divided by the
  rate among items not on the screening list.

## Predictions

| | Prediction | Fails if |
|---|---|---|
| P1 | Strict-flagged items are key errors at least twice as often as unflagged items | enrichment < 2 |
| P2 | Screening-flagged items are key errors at least 1.5 times as often as unflagged items | enrichment < 1.5 |
| P3 | At least 25% of key-error items are on the screening list | recall < 25% |
| P4 | Across subjects, the share of Redux items with any error correlates with the share of our items flagged on the screening list, Spearman ρ ≥ 0.3 | ρ < 0.3 |

Every prediction is reported as held or failed, with its number. A failed
prediction is published as a failure. If fewer than 200 items match across
subjects, the study is reported as underpowered rather than as a result.

## What a result would and would not license

- **If P1 holds:** the strict flag points at real answer-key errors on real
  data, at a measured rate. That rate, not the synthetic one, becomes the figure
  to quote — with its interval.
- **Not licensed either way:** that an unflagged item is correct; that Redux's
  labels are infallible (they are expert judgements, and experts disagree);
  that the rate transfers to benchmarks other than MMLU.
- An error of clarity (`bad_question_clarity`, `bad_options_clarity`) is not
  expected to produce a negative discrimination, which is why P1 to P3 are
  stated on key errors only.
