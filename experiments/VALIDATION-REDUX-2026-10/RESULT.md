# Our flags against human experts: four predictions, four held

Pre-registered in [PREREGISTRATION.md](PREREGISTRATION.md) (commit `671383b`)
before the two sources were joined. Reproduce with:

    python scripts/validate_against_redux.py --out result.json

## The question

Every accuracy figure this project had for its item flags came from synthetic
data with defects we planted, and was stated as an upper bound. This tests the
flags on **real questions judged by people**: MMLU-Redux 2.0, in which experts
re-annotated 100 questions in each MMLU subject (Gema et al., University of
Edinburgh; CC BY 4.0).

The flags are read unchanged from the item analysis of HELM MMLU in
`experiments/SURVEY-2026-09`, computed on up to sixty models (the first sixty in
HELM's manifest order). Nothing was re-run for this study.

## The join

**5,005 questions matched across 51 subjects**, by normalised question text. 95
Redux questions were dropped: 9 matched no HELM instance, 86 matched more than
one. None was missing from our reports.

## Result

| | Items | Answer-key errors (experts) | Rate | 95% interval | Against unflagged |
|---|---|---|---|---|---|
| Not on the screening list | 4,634 | 35 | 0.8% | 0.5 – 1.0% | — |
| Screening list (discrimination < 0) | 371 | 41 | 11.1% | 8.3 – 14.6% | **× 14.6** |
| Strict list (interval rule) | 73 | 16 | 21.9% | 14.0 – 32.7% | **× 29** |

- **Recall:** 41 of the 76 expert-labelled answer-key errors are on the screening
  list — **54%** (interval 43 – 65%), found without reading a single question.
- **Subject level:** the share of a subject's items with any expert-labelled
  error and the share we flag correlate at Spearman ρ = 0.31.

| | Prediction | Result | |
|---|---|---|---|
| P1 | Strict list enriched at least ×2 | ×29 | **held** |
| P2 | Screening list enriched at least ×1.5 | ×14.6 | **held** |
| P3 | Recall on the screening list at least 25% | 54% | **held** |
| P4 | Subject-level ρ at least 0.3 | 0.31 | **held**, by a hundredth |

## What it means in practice

**An expert who reviews the 7% of questions on the screening list finds more
than half of the answer-key errors.** Reviewing the 1.5% on the strict list
finds about one in five, at a rate of more than one error per five items read.
That is the use the flags were built for: deciding what a person reads first.

## What it does not mean — stated as plainly as the result

- **A flag is not a verdict.** On the strict list, 22% of items are answer-key
  errors. Exploratory, not pre-registered: 27% carry some expert-labelled
  defect (adding ambiguity, multiple correct answers, and questions needing an
  expert), so **73% of strict-flagged items were judged correct**. A flagged
  item is one to read, not one to delete.
- **Unflagged is not correct.** 35 answer-key errors sit among unflagged items,
  and a further 194 unflagged items carry another kind of defect.
- **P4 held by a hundredth.** It is reported as held because that is what was
  fixed, and it is the weakest of the four; it would not survive a stricter
  threshold.
- **The labels are expert judgements**, which disagree at the margin, and the
  rate is measured on MMLU. It may not transfer to other benchmarks.
- **The panel is sixty models in manifest order**, neither random nor strongest.

## Why this changes what we can claim

The synthetic characterisation said how often a planted defect is found, and
could only be an upper bound. This says what a flag is worth on real questions
that people checked: a flagged item is **14 to 29 times** more likely to carry
a wrong answer key than an unflagged one, and the screening list holds **more
than half** of all such errors. Those are the figures to quote, with their
intervals and with the 73% beside them.
