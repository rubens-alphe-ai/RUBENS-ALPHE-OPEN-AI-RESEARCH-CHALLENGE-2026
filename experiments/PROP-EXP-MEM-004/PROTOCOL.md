# PROP-EXP-MEM-004 — Handoff quiz: structure measured without a judge

Frozen before any trial. Its SHA-256 is recorded in the experiment manifest.
The executable rules are in `evaluation_policy.json`; the questions and their
answers are in `QUIZ.json`. All three are committed before the first trial.

## Why this experiment exists

MEM-001 to MEM-003 measured handoff quality with language-model judges on a
100-point rubric. Across those experiments the judges were the main source of
failure and noise: free shared capacity failed for hours and exhausted a whole
pre-registered ladder; judges miscomputed totals; one judge gave 100 to half
the answers; two judges differed by 20 points on the same answer; calibration
showed full marks for a complete answer and bands missed; and a capable
generator copied section keys that could reveal the condition to a judge.

MEM-004 asks the same question and removes the judge.

## Hypothesis

Holding information content constant, a project state presented as named
sections transfers more correct facts through a handoff than the same facts in
prose, without more invented facts.

## Design

**Stage 1 — handoff.** Identical to MEM-003: the generator
`qwen/qwen3.8-27b` (Groq, reasoning off, temperature 0.8, at most 1,000
tokens) reads `STATE_A.txt` (prose) or `STATE_B.json` (sections) — byte-
identical to MEM-002/003 — followed by `TEST_PROMPT.md`, and writes a handoff.
Thirty pairs, seeds 601–630, one stateless request per trial.

**Stage 2 — quiz.** A reader, `openai/gpt-oss-120b` (Groq, temperature 0,
reasoning low), receives **only one handoff text** and the 42 questions of
`QUIZ.json`, and returns one letter per question. It never sees the state, the
condition, other handoffs or the key. Handoffs are read in an order shuffled
from the protocol hash.

- 32 **fact** questions, each with one answer supported by the state, three
  distractors and "The text does not say."
- 10 **absent** questions about things the state never contains (model used,
  budget, a result, a date…). The only correct answer is "The text does not
  say"; any other answer is counted as an **invention**.
- Option order is shuffled per question from a fixed seed; "The text does not
  say" is always option E. The rendered key is stored in `results/quiz/`.

**Grading** is a comparison of letters by `scripts/handoff_quiz.py`. Missing
or invalid answers count as wrong, never as "does not say". A reader answer
with any missing or invalid letter is requested once more, and the last answer
is graded. An answer with no usable letter at all is not graded: the run stops
as incomplete and asks again on the next run, rather than guess.

## Measures

- **Primary:** fact accuracy (share of the 32 fact questions answered
  correctly), compared within each pair: structured minus baseline, in
  percentage points.
- **Secondary:** inventions (non-E answers to absent questions), summed per
  condition over the 30 handoffs (300 answers each).

## Decision rule (evaluated in this order)

1. **REJECT** if structured inventions exceed baseline inventions by more than
   5.
2. **PROVISIONAL_KEEP** if the mean paired delta is at least **+10 points** and
   the lower bound of its 95 % confidence interval (t distribution, 29 degrees
   of freedom) is above 0.
3. **REJECT** if the upper bound of that interval is below +10 points: an
   improvement of the size that matters is excluded.
4. Otherwise **INCONCLUSIVE**.

`FINAL_KEEP` is out of reach by design: one generator, one reader, no holdout.

## Pilot, before freezing

The reader was run once on an unrelated 60-word text about a bakery, with this
quiz: it answered "The text does not say" to all 42 questions and its JSON was
parsed without error. No MEM-004 state or handoff was involved, so the pilot
cannot favour either condition.

## Known limits, stated in advance

- The quiz measures transfer of facts and restraint from invention, not the
  quality of the proposed next action; that is deliberate.
- A handoff limited to 450 words cannot hold all 32 facts; scores well below
  100 % are expected in both conditions. The comparison is paired.
- One reader model; a reader that guesses instead of choosing E would add noise
  equally to both conditions. Its restraint is measured by the absent
  questions.
- Questions were written from the state by the same assistant that designed the
  experiment, after MEM-003's handoffs were generated but without reading any
  of them.
- Generator seeds on a hosted provider are pairing labels, not a determinism
  guarantee.
