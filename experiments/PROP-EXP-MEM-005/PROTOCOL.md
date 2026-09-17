# PROP-EXP-MEM-005 — Handoff checklist: does telling the writer what to keep help?

Frozen before any trial. Its SHA-256 is recorded in the experiment manifest.
Executable rules: `evaluation_policy.json`. Questions and key: `QUIZ.json`,
byte-identical to MEM-004's.

## Why this experiment exists

MEM-004 showed that reformatting the state (prose or sections) does not change
how many facts a handoff transfers (−0.9 points, 95 % CI −4.1 to +2.2). It also
showed where facts are lost: every error was an omission, and what was omitted
depended on what the writer chose to mention. The question moves from the
format of the state to the writer's selection.

## Hypothesis

Adding a short, generic handoff checklist after the state — naming the kinds of
items to carry over, with their status — increases the share of facts a reader
can recover from the handoff, without more invented facts.

## Conditions

| Manifest condition | Input | Meaning |
|---|---|---|
| `baseline` | `STATE_A.txt` | the prose state, byte-identical to MEM-004's baseline |
| `structured` | `STATE_C.txt` | the same bytes, then a blank line and the checklist |

The manifest's condition names are fixed by the tooling; here `structured`
means **checklist**. The checklist (the last paragraph of `STATE_C.txt`) names
only the kinds of items the state contains — mission, verified knowledge,
decisions and reasons, failures with causes and fixes, experiments and status,
next actions, open questions, rules in force — and asks for short factual
statements within the same length limit. It names no fact and no question of
the quiz, and it does not mention the project's name, the one fact no MEM-004
handoff carried.

Both conditions then receive the same `TEST_PROMPT.md` (under 450 words).

## Design

Identical to MEM-004 apart from the condition:

- generator `qwen/qwen3.8-27b` on Groq, reasoning off, temperature 0.8, at most
  1,000 tokens; thirty pairs, seeds 701–730;
- reader `openai/gpt-oss-120b` on Groq, temperature 0, reasoning low, at most
  1,500 tokens (MEM-004: 2,500; its answers need far less), sees one handoff
  and the 42 questions only;
- 32 fact questions, 10 absent-fact questions; letters graded by
  `scripts/handoff_quiz.py`; a partial reader answer is asked once more and the
  last one graded; an answer with no usable letter stops the run as incomplete.

Reader requests are now paced before sending, counting the output budget
against the provider's per-minute token limit.

## Decision rule (in this order)

1. **REJECT** if checklist inventions exceed baseline inventions by more than 5.
2. **PROVISIONAL_KEEP** if the mean paired delta in fact accuracy is at least
   **+5 points** and the lower bound of its 95 % confidence interval is above 0.
3. **REJECT** if the upper bound of that interval is below +5 points.
4. Otherwise **INCONCLUSIVE**.

The threshold is +5 rather than MEM-004's +10 because MEM-004's baseline was
89 %: +10 would require near-perfect handoffs and could not be reached even by
a real improvement. +5 points is about half of the facts the baseline lost.

## Known limits, stated in advance

- Same single generator, reader, state and quiz as MEM-004; a positive result
  would need replication with another generator and a holdout state.
- The checklist follows the state's own categories, and the quiz covers those
  categories, so a gain means "a checklist of the state's categories helps
  cover the state"; it does not show that any checklist helps any handoff.
- The checklist was written after MEM-004's results were known, from the
  categories of the state and not from the per-question results; the one
  question never answered in MEM-004 (the project's name) is deliberately not
  targeted.
- Baseline accuracy near 89 % leaves little room; the confidence interval, not
  the mean alone, decides.
