# Pre-registration: the defect diagnosis on questions the model cannot have seen

Written 2026-10-03T16:33:02Z (clock). It is committed and pushed before any
question is written, solved or diagnosed.

## Why

In DIAGNOSIS-REDUX-2026-10, deepseek-v4.1-flash judged flagged MMLU items
blind to the flag. Among the items it called KEY_WRONG, 43% carried an
expert-found key error; the flag alone gives 11%. All four predictions held.

Its first stated limit was contamination. MMLU and the MMLU-Redux annotations
are public, so the model may have memorised the questions or the labels. This
replication removes both: the questions are written today, and the errors are
planted today by a script.

## Design (`scripts/diagnose_unseen.py`, sha256 `944a15b8…` at this commit)

1. **Writing.** `google/gemini-3.6-flash` writes 500 new four-option
   questions: 20 subjects, 5 batches of 5. Questions that are malformed,
   duplicated, or have repeated options are dropped.
2. **Cleaning.** `minimax/minimax-m3` and `mistralai/mistral-large-2512`
   each answer every question blind. A question is kept only if both choose
   its key. The writer, the two solvers and the diagnoser come from four
   different families.
3. **Planting.** From the kept questions, 300 are drawn with
   `random.Random(20261003)`. In 60 of them (20%), drawn with the same
   generator, the key is moved to a random wrong option. If fewer than 300
   questions are kept, the run stops before any diagnosis, and that is
   reported. The design is not changed afterwards.
4. **Diagnosis.** `deepseek/deepseek-v4.1-flash` judges all 300 questions.
   It uses the first study's prompt, read from `scripts/diagnose_flagged.py`
   (sha256 `75beef9d…`, unchanged since the parse fix of the first study),
   with the same settings: temperature 0, reasoning effort low, 1,500 output
   tokens and one retry. An item without a verdict counts as missed in U2 and
   is excluded from the U1 denominator.
5. **Budget.** At most 5 USD. The script refuses to run if its pessimistic
   estimate is higher.

## Predictions

| ID | Prediction | Threshold |
|---|---|---|
| U1 | Among items called KEY_WRONG, the share that are planted errors is at least twice the base rate of 20%, and its 95% Wilson lower bound is above 20% | rate ≥ 0.40 and lower bound > 0.20 |
| U2 | Share of the 60 planted errors called KEY_WRONG | ≥ 0.50 |
| U3 | KEY_WRONG on the 240 clean questions | ≤ 0.10 |
| U4 | When a planted error is called KEY_WRONG, the option it names as correct is the original key | ≥ 0.80 |

**Exploratory, not a prediction.** The precision that U2 and U3 would give at
the 11.1% key-error prevalence of the flagged items in the first study.

## How the two studies bracket the truth

- **The first study used natural errors, but memorisation was possible.**
- **This study removes memorisation, but uses artificial errors.** A planted
  wrong key on a question two solvers found unambiguous is easier to see than
  a subtle natural error.

**If both studies hold,** the claim we may make is this: on flagged items, the
model's verdict is a useful first sort, and it does not rest on memorisation.
**If this one fails,** the first study's result is treated as possibly
memorised and is not sold as a capability.
