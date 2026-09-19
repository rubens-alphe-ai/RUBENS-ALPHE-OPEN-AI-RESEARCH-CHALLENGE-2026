# PROP-EXP-MEM-007 — The checklist with a third generator family

Frozen before any trial. Executable rules: `evaluation_policy.json`. Questions
and key: `QUIZ.json`, byte-identical to MEM-004, MEM-005 and MEM-006.

## Why this experiment exists

MEM-005 measured +4.1 points (95 % CI +1.5 to +6.6) from a generic handoff
checklist, below the pre-registered +5 bar. MEM-006 repeats it with another
generator and another reader. A result that holds for two model pairs is
better than one; three independent pairs make the estimate worth pooling.

MEM-007 adds a third generator family, DeepSeek, and **keeps MEM-005's reader
model**, so the generator is the only thing that differs from MEM-005. Whatever
MEM-006 returns, this experiment asks the same question of a different writer.

## What changes, and what does not

| | MEM-005 | MEM-006 | MEM-007 |
|---|---|---|---|
| Generator | `qwen/qwen3.8-27b` (Alibaba) | `moonshotai/kimi-k3` (Moonshot) | `deepseek/deepseek-v4.1-flash` (DeepSeek) |
| Reader | `openai/gpt-oss-120b` | `z-ai/glm-5.3` | `openai/gpt-oss-120b`, same model as MEM-005 |
| Pairs | 30 | 60 | 60 (seeds 901–960) |
| States, checklist, prompt, quiz, key, rule | — | identical | identical |

## Design

Identical to MEM-005 and MEM-006 apart from the models: the generator reads
`STATE_A.txt` or `STATE_C.txt` (same bytes plus the checklist) followed by
`TEST_PROMPT.md`, temperature 0.8, at most 1,500 output tokens; the reader sees
one handoff and the 42 questions and returns one letter each; letters are graded
against the frozen key.

A reader ladder is pre-registered: if the first reader cannot complete every
reading, its readings are set aside and the next reader reads all of them again.
Both rungs are the same model served by two providers, so a provider outage does
not change what reads the handoffs.

## Money

This is the project's first experiment paid for rather than run on free quotas.

- The owner set a ceiling of **0.50 USD for this experiment**, recorded in
  `evaluation_policy.json` as `budget.max_usd`.
- `scripts/cost_guard.py` prices the run before the first call, pessimistically
  (full prompts, full output budgets, every call), and the runner refuses to
  start if the estimate exceeds the ceiling.
- Expected cost at the providers' published prices is about 0.19 USD.
- Paying changes how long the run takes and nothing else: same states, same
  quiz, same key, same threshold, same grader.

## Decision rule (in this order)

1. **REJECT** if checklist inventions exceed baseline inventions by more than 5.
2. **PROVISIONAL_KEEP** if the mean paired delta is at least **+5 points** and
   the lower bound of its 95 % confidence interval is above 0.
3. **REJECT** if the upper bound of that interval is below +5 points.
4. Otherwise **INCONCLUSIVE**.

Unchanged from MEM-005 and MEM-006, including the threshold.

## Known limits, stated in advance

- Same single state and quiz as MEM-004 to MEM-006; the holdout
  (`experiments/HOLDOUT-2026-09/`) stays sealed until a candidate passes.
- Generator and reader are both served through OpenRouter here, so a gateway
  fault would affect both stages; their model families are unrelated, and the
  reader ladder's second rung uses another provider for the same model.
- Pooling MEM-005, MEM-006 and MEM-007 afterwards is a planned analysis, not a
  pre-registered decision: any pooled estimate is reported as exploratory.
- The checklist was written after MEM-004, by the same author as the quiz.
