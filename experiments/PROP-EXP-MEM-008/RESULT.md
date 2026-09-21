# PROP-EXP-MEM-008 — Result


> **Corrected 2026-09-21.** Some numbers below moved after a defect was found in the code that produced them. The verdict is unchanged. See [`docs/CORRECTIONS-2026-09-21.md`](../../docs/CORRECTIONS-2026-09-21.md) for every number that moved and why the stored files were not overwritten.

**The instruction helps**, on all three documents, under the rule frozen in
`PROTOCOL.md` before the first trial: at hop 3 the checklist keeps at least
10 points more facts than a free summary, with the lower bound of the 95 %
confidence interval above 0, on at least two of three documents.

| Document | Checklist vs summary at hop 3 | 95 % CI |
|---|---|---|
| Clinic | **+31.9 points** | +17.0 to +46.8 |
| Vineyard | **+16.7 points** | +12.8 to +20.6 |
| Observatory | **+20.8 points** | +15.3 to +26.4 |

No invented fact anywhere: 0 of 1,152 absent-fact answers across all
strategies, documents and depths. The rejection clause on inventions does not
apply.

## The finding that was not expected

Loss does not accumulate hop after hop. It happens almost entirely at the
**first** compression, and the chain then holds.

| Clinic | hop 1 | hop 3 | hop 5 |
|---|---|---|---|
| Checklist | 96.4 % | 94.2 % | 91.3 % |
| Sections | 84.1 % | 81.2 % | 80.4 % |
| Summary | 65.2 % | 62.3 % | 61.6 % |

| Observatory | hop 1 | hop 3 | hop 5 |
|---|---|---|---|
| Checklist | 91.7 % | 91.7 % | 92.4 % |
| Summary | 77.1 % | 70.8 % | 70.1 % |

A free summary destroys a third of the document immediately, then transmits the
remainder almost intact. A handoff written to carry facts loses little at the
first step and stays there.

**What kills a project's memory is not the number of handoffs. It is the
quality of the first one.** Everything downstream inherits that loss, because
each writer can only pass on what it received.

This also revises the exploratory run of 2026-09-18, which reported 39 % for
summaries at hop 3. That run lost 15 of 24 chains, unevenly across strategies,
and was recorded as exploratory for that reason. The corrected figure is 62 to
80 % depending on the document.

## Strategies, ranked and qualified

1. **Checklist** — best or tied best on all three documents, at every depth,
   within the word budget (117 to 127 words of the 150 allowed).
2. **Sections** — consistently second, +9 to +19 points over the control.
3. **Facts only** — unstable: best on the vineyard, **worse than a free
   summary** on the clinic. It writes to the limit and is cut, so its content
   is decided by where the truncation falls rather than by what matters.
4. **Summary** (control) — always last.

## Design

- 3 documents of about 300 words from unrelated domains, written for this
  experiment; each with a quiz built and machine-verified by
  `scripts/build_quiz_from_document.py` (23 to 24 fact questions, 8 absent-fact
  questions each).
- 4 strategies × 6 repeats × 3 documents = 72 chains of 5 handoffs, read at
  hops 1, 3 and 5: 360 writing calls, 216 readings.
- Every handoff cut to 150 words before being passed on, identically for every
  strategy, so length cannot buy an advantage. Cuts are counted per strategy.
- Writer `deepseek/deepseek-v4.1-flash`, reader `openai/gpt-oss-120b`,
  no shared family. One chain of 72 failed and is listed in `report.json`.
- Cost: about 1.30 USD, under the ceiling of 1.50 written in the policy.

## Limits, as registered in advance

- The three documents and the instructions compared share an author.
- Machine-generated quizzes: a question that passes every check can still be
  poorly worded.
- One writer and one reader model. The instruction's effect on a single handoff
  was replicated across three writer families in MEM-005 to MEM-007; the chain
  result has not been.
- The holdout (`experiments/HOLDOUT-2026-09/`) stays sealed.
