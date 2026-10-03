# Result: a cheap model can sort flagged items by probable defect

Scored 2026-10-03T15:10:24Z. Pre-registered in `PREREGISTRATION.md` (commit
`c968dd7`, pushed before any model was asked). Model:
`deepseek/deepseek-v4.1-flash`. Items: 371 screening-flagged MMLU items and
200 unflagged controls. Labels: MMLU-Redux 2.0 experts.

## The four predictions held

| ID | Prediction | Threshold | Observed | |
|---|---|---|---|---|
| D1 | Expert key-error rate among items the model calls KEY_WRONG | ≥ 0.222, lower bound > 0.111 | **24 / 56 = 42.9%** [30.8, 55.9] | held |
| D2 | Share of the 41 expert key errors the model calls KEY_WRONG | ≥ 21 of 41 | **24 / 41 = 58.5%** [43.4, 72.2] | held |
| D3 | Expert any-defect rate among any non-OK verdict | ≥ 0.336, lower bound > 0.224 | **47 / 92 = 51.1%** [41.0, 61.1] | held |
| D4 | KEY_WRONG on unflagged controls | ≤ 10% | **3 / 200 = 1.5%** [0.5, 4.3] | held |

## What this means for a report

Among flagged items, the flag alone points to a key error one time in nine
(11.1%). With the model's verdict added:

- **"Probably a wrong key"** (56 items): an expert-found key error in 43% of
  them, about four times the flag alone.
- **"Probably fine"** (234 items): an expert-found key error in 6 of them
  (2.6%), and a defect of any kind in 22 (9.4%).

A reader can therefore start with the 92 items the model calls defective. They
hold 47 of the 83 defects among the flagged items (57%). The cost was under one dollar for 571
items.

| Model verdict on flagged items | Items | Expert key error | Expert defect of any kind |
|---|---|---|---|
| KEY_OK | 234 | 6 | 22 |
| KEY_WRONG | 56 | 24 | 28 |
| MULTIPLE_CORRECT | 11 | 3 | 4 |
| NO_CORRECT_ANSWER | 16 | 2 | 7 |
| UNCLEAR | 9 | 0 | 8 |
| no verdict | 45 | 6 | 14 |

## Limits

- **Contamination.** MMLU and MMLU-Redux are public. The model may have seen
  the questions or the expert annotations, so this is an upper bound for a
  client's unseen test. It must be repeated on a test the model cannot have
  seen before being sold as a measured capability on private tests.
- **No verdict on 51 of 571 items (8.9%).** The model spent its 1,500-token
  budget reasoning and returned no answer, even after the pre-registered
  retry. Under the pre-registered rule these count as missed in D2, which is
  conservative: 6 of the 41 key errors are among them. A larger budget would
  probably reduce this; it was not changed after the fact.
- **One model, one prompt.** This is not a comparison of models.
- **Precision is 43%, not 100%.** A KEY_WRONG verdict says what to check
  first; it is not a finding on any single item.

## Deviation

The first run stopped on a parsing bug: a verdict whose `best_option` was
null raised an error instead of being read. The fix is one condition in
`parse()`; a regression test was added.
- **Unchanged:** the prompt, the sample, the model, the thresholds and the
  scoring. `git diff c968dd7 -- scripts/diagnose_flagged.py` shows the whole
  change.
- **Recovery:** answers already stored were kept; items that crashed before
  being stored were asked again.
