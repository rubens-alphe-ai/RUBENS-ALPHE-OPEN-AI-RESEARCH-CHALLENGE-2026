# PROP-EXP-MEM-006 — Does the handoff checklist survive other models?

Frozen before any trial. Executable rules: `evaluation_policy.json`. Questions
and key: `QUIZ.json`, byte-identical to MEM-004's and MEM-005's.

## Why this experiment exists

MEM-005 found the project's first positive signal: a generic handoff checklist
raised fact transfer by +4.1 points (95 % CI +1.5 to +6.6), below the
pre-registered +5 bar, with zero inventions. Two things were left open.

1. **Models.** One generator (`qwen/qwen3.8-27b`) wrote every handoff and one
   reader (`openai/gpt-oss-120b`) answered every quiz. The effect could belong
   to that pair rather than to the checklist.
2. **Precision.** With thirty pairs the interval is about five points wide, too
   wide to separate "just below the bar" from "at the bar".

MEM-006 changes the models and doubles the pairs. Everything else — states,
checklist, prompt, quiz, key, grading, thresholds — is unchanged.

## What changes, and what does not

| | MEM-005 | MEM-006 |
|---|---|---|
| Generator | `qwen/qwen3.8-27b` (Groq, Alibaba family) | `moonshotai/kimi-k3` (NVIDIA, Moonshot family) |
| Reader | `openai/gpt-oss-120b` (Groq) | `z-ai/glm-5.3` (NVIDIA, Zhipu family) |
| Pairs | 30 (seeds 701–730) | 60 (seeds 801–860) |
| States, checklist, prompt, quiz, key, rule | — | identical |

Neither model was used in MEM-005, and the reader's family differs from the
generator's.

## Design

- **Stage 1:** the generator reads `STATE_A.txt` (baseline) or `STATE_C.txt`
  (the same bytes plus the checklist), then `TEST_PROMPT.md` (under 450 words),
  temperature 0.8, at most 2,000 tokens, one stateless request per trial.
- **Stage 2:** the reader sees one handoff and the 42 questions, and returns one
  letter per question; letters are graded against the frozen key.
- **Reader ladder** (new, pre-registered): if the first reader cannot complete
  every reading, its readings are set aside in `results/quiz/abandoned/` and the
  next reader reads **all** handoffs again. One experiment is never graded by
  two readers. Order: GLM 5.3 (NVIDIA), Kimi K3 (NVIDIA), gpt-oss-120b (Groq).

## Decision rule (in this order)

1. **REJECT** if checklist inventions exceed baseline inventions by more than 5.
2. **PROVISIONAL_KEEP** if the mean paired delta is at least **+5 points** and
   the lower bound of its 95 % confidence interval is above 0.
3. **REJECT** if the upper bound of that interval is below +5 points.
4. Otherwise **INCONCLUSIVE**.

Identical to MEM-005's rule, including the threshold, which is therefore not
adjusted to the result MEM-005 produced.

## What each outcome would mean

- **PROVISIONAL_KEEP:** the checklist helps by at least the size the project
  called meaningful, with two unrelated model families. The sealed holdout
  (`experiments/HOLDOUT-2026-09/`) then becomes the next test.
- **REJECT:** the effect is smaller than +5 points even with sixty pairs. The
  checklist would remain a real but minor improvement, recorded as such.
- **INCONCLUSIVE with a positive interval:** the effect exists but its size
  stays undecided; more pairs would be needed.

## Known limits, stated in advance

- Still one state and one quiz; the holdout stays sealed until a candidate
  passes.
- Generator and reader are both served by NVIDIA, so a provider-wide fault
  would affect both stages; their model families are unrelated.
- Kimi K3 took about 108 seconds per request in a neutral probe, so generation
  takes hours; this affects duration only.
- The checklist was written after MEM-004, by the same author as the quiz.
