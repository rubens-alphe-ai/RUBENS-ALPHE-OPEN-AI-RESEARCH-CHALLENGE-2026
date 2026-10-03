# Pre-registration: can a cheap model say what is wrong with a flagged item?

Written 2026-10-03T14:47:50Z (clock), before any model was asked about any of
these items. Committed before the run; the commit that adds this file is the
record of that order.

## Why

The item flags find where the expert-found key errors are. In
VALIDATION-REDUX-2026-10 (5,005 MMLU items matched to MMLU-Redux 2.0 expert
labels), 371 items are on the screening list. Among them:

- 41 (11.1%) carry an expert-found key error;
- 83 (22.4%) carry an expert-found defect of any kind.

A flag tells a buyer what to read first, but about four flagged items in five
are fine. This tests whether one inexpensive model, blind to the flag, can sort
the flagged items into "probably fine" and "probably this defect". That would
let a report say what is likely wrong, not only where to look.

## Design

- **Items.** All 371 screening-flagged items, plus 200 unflagged items drawn
  with `random.Random(20261003).sample` from the unflagged items sorted by
  (subject, item id). 571 items in total.
- **What the model sees.** The question, its four options and the key, taken
  from the MMLU-Redux 2.0 row (original MMLU key), with the prompt that is
  fixed in `scripts/diagnose_flagged.py` (sha256 `0f25ef81…eeb0` at this
  commit). The model is never told whether an item was flagged, nor what the
  experts said.
- **Model.** `deepseek/deepseek-v4.1-flash` through OpenRouter, temperature 0,
  reasoning effort low, at most 1,500 output tokens.
- **Retries.** One retry on an unusable answer. An item still without a valid
  verdict counts as **NO_VERDICT**, which counts as "not detected" in D2 and is
  excluded from the D1 and D3 denominators.
- **Budget.** At most 3 USD. The script refuses to run if its pessimistic
  estimate is higher; that estimate is 1.08 USD.
- **Labels.** The expert labels come from the stored
  `experiments/VALIDATION-REDUX-2026-10/result.json` (sha256 `479aa393…0d74`).
  They are not re-derived.

## Predictions (all on the 371 flagged items, except D4)

| ID | Prediction | Threshold |
|---|---|---|
| D1 | Among items the model calls KEY_WRONG, the expert key-error rate is at least twice the flag-only rate, and its 95% Wilson lower bound is above the flag-only rate | rate ≥ 0.222 and lower bound > 0.111 |
| D2 | The model calls KEY_WRONG on at least half of the 41 expert key errors | ≥ 21 of 41 |
| D3 | Among items the model calls anything other than KEY_OK, the expert any-defect rate is at least 1.5 times the flag-only rate, and its lower bound is above that rate | rate ≥ 0.336 and lower bound > 0.224 |
| D4 | On the 200 unflagged controls, the model calls KEY_WRONG on at most 10% | ≤ 20 of 200 |

## What each outcome would mean

- **D1 and D2 hold:** a report can add a "probable diagnosis" column for
  flagged items, stated with its measured precision.
- **D1 holds, D2 fails:** the model's KEY_WRONG verdicts are worth reading
  first, but they miss too many errors to replace reading the flagged list.
- **D1 fails:** no diagnosis column. The flag stays "read this first".
- **D4 fails:** the model over-calls errors and cannot be used on unflagged
  items.

## Known threats, stated in advance

- **Contamination.** MMLU and MMLU-Redux (2024) are public, so the model may
  have seen the questions, or the Redux annotations themselves. A success here
  is therefore an upper bound for unseen client tests. It must be repeated on
  a test the model cannot have seen before it is sold as a measured
  capability.
- **One model, one prompt.** This is not a comparison of models.
- **No outcome is reported as a verdict on any individual item.**
