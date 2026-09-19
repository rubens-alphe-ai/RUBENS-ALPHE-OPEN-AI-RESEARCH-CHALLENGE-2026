# PROP-EXP-MEM-006 — the second reading was never lost

**Nothing was re-read and no model was called, because nothing needed to be.**
`decision-kimi-reader.json` was reported as resting on data that was never
stored. It is not. All 120 of that reader's answers are in this repository, and
the published summary recomputes from them field for field.

## What was said to be lost

`experiments/PROP-EXP-MEM-007/CORRECTION.md` lists this file under "the two
claims that are not checkable at all":

> **`results/decision-kimi-reader.json`** — a second, independent reading
> (+6.61 pp, CI +4.29 to +8.94, 60 pairs) by `reader-nvidia-kimi-k3`. **No
> directory of that reader's answers exists in the repository.**

`scripts/regression_suite.py` agreed, and `tests/test_regression_suite.py`
recorded it in `KNOWN_UNVERIFIABLE`.

## Where the answers actually are

`experiments/PROP-EXP-MEM-006/results/quiz/abandoned/reader-nvidia-kimi-k3/`

120 records — 60 baseline, 60 structured — each with the reader's raw letters,
its `reader_id`, the SHA-256 of the handoff it read, its `read_at_utc` and its
grade, plus the reader's unparsed reply beside each one as
`<trial>.attempt1.raw.txt`, and an `answer-key.json`. 253 files in all.

This is exactly where `PROTOCOL_DEVIATIONS.md` D3 said the reading was put, in a
sentence written before the verdict:

> the Kimi reading is set aside in `results/quiz/abandoned/reader-nvidia-kimi-k3/`
> with its decision preserved as `decision-kimi-reader.json`, both published.

The record was never wrong. The suite was looking in the wrong place: for a
decision named `decision-<slug>.json` it searched only `results/quiz-<slug>/`
and `results/<slug>/`, and the folder here is named after the *reader*
(`reader-nvidia-kimi-k3`) while the file is named after a *slug*
(`kimi-reader`). The two names never meet, so the suite concluded the evidence
did not exist rather than that it could not find it.

## What the stored answers give

Regrading all 120 records against the key rebuilt from `QUIZ.json`, and applying
the rule in `evaluation_policy.json`:

| Number | Recomputed from the stored answers | Published in `decision-kimi-reader.json` |
|---|---|---|
| `decision` | PROVISIONAL_KEEP | PROVISIONAL_KEEP |
| `pairs` | 60 | 60 |
| `mean_paired_delta_pp` | 6.614583333333333 | 6.614583333333333 |
| `sd_delta_pp` | 9.189399857373742 | 9.189399857373742 |
| `ci95_delta_pp` | +4.289344349529045 to +8.939822317137622 | identical |
| `inventions` | 0 baseline, 0 structured | 0 and 0 |
| `pairs_structured_better` / `worse` / `equal` | 42 / 11 / 7 | 42 / 11 / 7 |

**Every field is identical, to the last digit.** The stored key also matches the
key rebuilt from `QUIZ.json`, the stored rendering matches the rebuilt
rendering, and all 120 per-record `grade` blocks reproduce from their own
answers. Model calls made for this: **zero**. Cost: **zero**.

## What was done about it

`scripts/regression_suite.py` now locates a set-aside reading by the `reader`
field of the decision that published it, which is the only name that links the
two. Two tests pin the behaviour: one that a reading filed under its reader is
found, and one that a folder whose records name a *different* reader is refused
rather than regraded — regrading one reader's verdict from another's answers
would turn a disagreement between two models into a published number appearing
to move.

`decision-kimi-reader.json` was not edited, and neither were any of the 120
records. `PROP-EXP-MEM-006` now reports `reproduced` with 397 numbers checked,
and its entry has been removed from `KNOWN_UNVERIFIABLE` in
`tests/test_regression_suite.py` — removed because the evidence was found, not
because the claim was accepted.

## What this does not change

The Kimi reading is still **not** the verdict of record, and this does not
reinstate it. D3 set it aside because `moonshotai/kimi-k3` wrote every handoff
in this experiment, and a model reading its own writing is not an independent
reader. That objection is about who read, and is untouched by where the answers
were filed. The verdict of record remains `decision.json` (+5.89 pp, by
`openai/gpt-oss-120b`), with `cross-read-deepseek/` (+5.05 pp) beside it. All
three now reproduce from stored answers.

## The finding underneath

The correction's claim was that two published numbers rested on data that was
never stored. For this one the data was stored, in the place the protocol named,
and the tool that checks the promise could not see it. An automated check that
reports *unverifiable* can be wrong in that direction too, and this one was — it
understated what the project could show. That failure is quieter than a false
*reproduced* and it was believed for as long as nobody opened the folder.
