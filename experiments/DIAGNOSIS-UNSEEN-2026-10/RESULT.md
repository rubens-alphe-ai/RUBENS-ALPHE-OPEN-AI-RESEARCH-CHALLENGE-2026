# Result: on unseen questions, the diagnosis does not rest on memorisation

Scored 2026-10-03, after the pre-registration (commit `1169596`) and its two
amendments made before any diagnosis (`e06b1a9`: budget cap; `9797b65`:
second solver).

## Pipeline

| Stage | Count |
|---|---|
| Questions written by `google/gemini-3.6-flash` (20 subjects) | 466 well-formed, out of 500 requested |
| Kept: `minimax/minimax-m3` and `qwen/qwen3.5-122b-a10b` both chose the key | 428 |
| Drawn for the test | 300 |
| Key moved to a wrong option (planted) | 60 |

## The four predictions held

| ID | Prediction | Threshold | Observed | |
|---|---|---|---|---|
| U1 | Planted share among items called KEY_WRONG | ≥ 0.40, lower bound > 0.20 | **59 / 59 = 100%** [93.9, 100] | held |
| U2 | Planted errors called KEY_WRONG | ≥ 0.50 | **59 / 60 = 98.3%** [91.1, 99.7] | held |
| U3 | KEY_WRONG on the 240 clean questions | ≤ 0.10 | **0 / 240** [0, 1.6] | held |
| U4 | When caught, names the original key as correct | ≥ 0.80 | **59 / 59** [93.9, 100] | held |

- **The one planted error not caught** got no verdict: the model spent its
  token budget reasoning. It is counted as missed, as pre-registered.
- **On the clean questions**, there were 238 KEY_OK verdicts, 2 without a
  verdict and no other verdict at all.
- **Exploratory: precision at the 11.1% prevalence of the first study.**
  - With the observed rates, it is 1.0, but that only reflects zero false
    alarms.
  - Using the upper bound of the false-alarm interval (1.6%) gives a
    conservative figure of about 0.88.

Cost: about 3 USD of API usage, including the abandoned solver's calls.

## What the two studies say together

| | DIAGNOSIS-REDUX (natural errors) | DIAGNOSIS-UNSEEN (planted errors) |
|---|---|---|
| Could the model have memorised the items or the labels? | Yes | No: the items were written today and the errors planted by a script |
| Precision of KEY_WRONG | 43% | 100% |
| Errors caught | 59% | 98% |
| KEY_WRONG on items without an error | 1.5% of unflagged controls | 0% of clean questions |

**Memorisation.** The model's ability to spot a wrong key does not depend on
having seen the items. It detects an error by solving the question, and it
names the right answer every time it catches one.

**Natural errors are harder.** A key moved to a plainly wrong option on a
question two other models found unambiguous is the easiest case. Errors in a
real test are subtler: a disputed fact, a nearly right distractor, an
ambiguous stem.

**The natural-error figures are the ones to quote.** For a client's test, the
expected performance is nearer the first study (43% precision, 59% of errors
caught) than this one. This study shows that those figures are not an
artefact of memorisation.

## Limits

- **Artificial errors, so this is an upper bound for detection.**
- **One diagnosing model and one prompt.**
- **The questions were written by another model.** Their difficulty and style
  differ from human-written exam items.
- **The kept questions are easy for models by construction:** two solvers
  answered them correctly.

## Files

- `written/`: the generated batches.
- `solved/`: each solver's answers, including the 164 abandoned Mistral
  answers.
- `sample.json`: the 300 items, with the planted ones marked.
- `diagnosed/`: the raw verdicts.
- `result.json`: the scores.
