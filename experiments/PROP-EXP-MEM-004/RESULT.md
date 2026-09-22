# PROP-EXP-MEM-004 — Result


> **Effective length, measured 2026-09-22.** This quiz declares 32 fact questions and measures with about six: twenty-four are answered correctly by every reader in every trial. The effect below is real and its direction replicates, but it rests on a handful of items, and that is why a different reader moves its magnitude. See [docs/CORRECTIONS-2026-09-21.md](../../docs/CORRECTIONS-2026-09-21.md) and `scripts/item_analysis.py`.

**Decision: REJECT** (`IMPROVEMENT_BELOW_THRESHOLD_EXCLUDED`), decided
2026-09-17 by `scripts/run_quiz_experiment.py` under the rule frozen in
`PROTOCOL.md` (commit 13a25a0, before the first trial).

**Hypothesis not supported, and this time the answer is precise.** Presenting
the same facts as named sections instead of prose made no measurable
difference to how many facts a capable generator's handoff transferred. An
improvement of 10 points, the size the project set as meaningful, is excluded
by the data.

## Numbers

Thirty pairs, sixty handoffs, sixty readings, no missing or unusable answer, no
re-request needed.

| | Baseline (prose) | Structured (sections) |
|---|---|---|
| Mean fact accuracy (32 questions) | 89.0 % | 88.0 % |
| Wrong facts asserted | 0 | 0 |
| Facts omitted ("the text does not say") | 106 of 960 | 115 of 960 |
| Inventions (10 absent questions × 30) | 0 of 300 | 0 of 300 |

- Mean paired delta, structured minus baseline: **−0.9 points**
- 95 % confidence interval: **−4.1 to +2.2 points** (t, 29 df)
- Pairs: structured better 12, worse 12, equal 6

The upper bound (+2.2) is far below the +10 threshold, so rule 3 applies.

## What the handoffs did

- **Every error was an omission, none a false statement.** Across 1,920 fact
  answers the reader never chose a wrong option; when a handoff lacked a fact,
  the reader said so. Across 600 absent-fact answers it never invented one.
  Both the generator's handoffs and the reader were, in this sense, honest.
- **Structure changed what was kept, not how much.** The largest differences
  per question went both ways: the rule "an agent may propose, but evaluation is
  required before canonical state changes" survived in 10 of 30 prose handoffs
  and 2 of 30 structured ones; the reason for using GitHub Actions survived in
  22 prose and 28 structured. Over all questions these cancel out.
- **One question was never answerable:** the project's name (Q32) appeared in
  no handoff, in either condition. It lowers both means equally and does not
  affect the paired comparison.
- Fourteen of 32 questions were answered correctly in all sixty handoffs.

## What this result can and cannot say

It can say: for `qwen/qwen3.8-27b` writing a handoff of under 450 words from
these 32 facts, prose and sections transfer the same amount of correct
information, with no invented facts in either.

It cannot say that structure never matters: one generator, one reader, one
project state, and a handoff format (a free-text summary) that re-expresses the
state in the generator's own words. Structure might matter for a smaller
model, a longer state, or a handoff that must preserve the state verbatim.

## Why this result is more trustworthy than MEM-002

- No judge model: grading is a comparison of letters, reproducible from
  `results/quiz/`.
- No protocol deviation was needed.
- Thirty pairs and 32 questions per handoff give a confidence interval about
  6 points wide, narrow enough to exclude the effect of interest.
- The experiment ran unattended from start to verdict.

## Limits observed

- The reader, `openai/gpt-oss-120b` on Groq's free tier, hit the per-minute
  token limit 108 times; each was retried automatically, but reading took
  7.2 hours instead of about 30 minutes. Pacing before each request, rather
  than after an error, would remove most of that.
- The quiz key was written by the assistant that designed the experiment. It
  was committed before any handoff existed and is public for review.

## Consequence for the project

Three experiments (MEM-002, MEM-003 design, MEM-004) now point the same way:
reformatting the same facts into sections is not the lever for handoff
fidelity with capable models. The next question worth testing is not *format*
but *content selection*: which facts a handoff must carry, and whether telling
the generator which facts matter (e.g. rules and decisions, which were most
often dropped) improves transfer.
