# PROP-EXP-MEM-008 — How fast does a handoff decay, and does the instruction slow it down?

Frozen before any trial. Executable rules: `evaluation_policy.json`. Documents
and their quizzes are committed with this file, before the first run.

## Why this experiment exists

MEM-004 and MEM-005 measured a single handoff and found small effects: the state's
format changed nothing (−0.9 points), an instruction about which kinds of item to
carry gained +4.1 points, below the bar set in advance.

An exploratory benchmark on 2026-09-18 suggested we were measuring in the wrong
place. Passed along three times, each writer seeing only what the previous one
wrote, a free summary kept 39 % of the facts while an instructed handoff kept
66 % — a gap of 27 points, ten times what a single hop showed. That run is
recorded as exploratory: its tooling was written the same day, one strategy
ignored the length limit and so wrote three times more, and it used a single
document.

MEM-008 asks the same question properly.

## Hypothesis

Across repeated handoffs, an instruction naming the kinds of item to carry
preserves more facts than a free summary, at equal length, on documents from
unrelated domains, without more invented facts.

## Design

**Documents.** Three handover notes of about 300 words, in unrelated domains
(`documents/clinic.md`, `documents/vineyard.md`, `documents/observatory.md`),
written for this experiment. Each has its own quiz built by
`scripts/build_quiz_from_document.py` and kept only where every question passed
its checks: a verbatim supporting quote containing the answer, no wrong option
present in the document, and every absent-fact question confirmed unanswerable
by a second model reading the whole text.

**Strategies**, each receiving the same instruction to stay under 150 words:

| Name | Instruction |
|---|---|
| `summary` (control) | summarise for whoever takes this over |
| `checklist` | carry as many distinct facts as possible, each with its status: established, decided and why, failed and fixed, planned, open, rules in force |
| `sections` | named sections, one fact per line |
| `facts_only` | list the facts, one per line, each understandable alone |

**Chain.** For each document, strategy and repeat, the writer produces a handoff
from the document, then a handoff from that handoff, up to five times. Every
handoff is **cut to 150 words before it is passed on**, identically for every
strategy: in the exploratory run one strategy wrote 312 words against 108 for the
control, so its advantage was partly length. Cuts are counted and reported.

**Measurement.** After hops 1, 3 and 5 a reader that never saw the document
answers that document's quiz from the handoff alone. Letters are compared to the
frozen key. No model scores anything.

**Volume.** 3 documents × 4 strategies × 6 repeats = 72 chains, 360 writing calls
and 216 reading calls.

**Models.** Writer `deepseek/deepseek-v4.1-flash`, reader `openai/gpt-oss-120b`,
both through OpenRouter, reasoning disabled for the writer and low for the
reader. The writer's family is not the reader's.

## Decision rule

Per hop depth, paired by chain against the control:

1. **The instruction helps** if, at hop 3, `checklist` keeps at least **10 points**
   more facts than `summary` and the lower bound of the 95 % confidence interval
   is above 0, **on at least two of the three documents**.
2. **It does not help** if the upper bound of that interval is below 10 points on
   at least two documents.
3. Otherwise **inconclusive**.
4. Whatever the above, the result is **rejected** if `checklist` produces more
   invented answers than `summary` by more than 5 across the experiment.

Reported alongside, without being part of the rule: the decay curve at hops 1, 3
and 5 for every strategy, per document and pooled.

## Known limits, stated in advance

- The three documents were written by the same assistant that wrote the
  instructions being compared. They describe unrelated domains and contain no
  wording from the instructions, but a reader should weigh that.
- The quizzes are machine-generated and machine-checked; a question that survives
  every check can still be poorly worded.
- One writer, one reader. A replication with other models is the next step, and
  the tooling is public so anyone can run it.
- Cutting at 150 words penalises verbose strategies by design: the comparison is
  about what a fixed budget carries, not about who writes longest.
- Trials that fail are written down and counted; if failures fall unevenly across
  strategies by more than 10 % of runs, the experiment is reported as unusable
  rather than analysed, because failures are not random.
