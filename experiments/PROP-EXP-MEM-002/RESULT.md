# PROP-EXP-MEM-002 — Result

**Decision: REJECT** (`CRITICAL_FABRICATION_CONFIRMED_BY_TWO_EVALUATORS`),
adjudicated 2026-09-16 by `scripts/adjudicate_evaluations.py`, V4 contract.

**Hypothesis not supported.** Presenting the same facts as named sections did
not improve blind handoff fidelity over continuous prose. Both evaluators gave
the structured condition a lower mean score, and neither difference is
distinguishable from noise with nine pairs.

Both scorecards were frozen (commit 57e84d2 of the archive) before the
condition map was read.

## Who evaluated

| Role | Model | Provider |
|---|---|---|
| Generator | `llama3.2:3b`, temperature 0.8, nine seeds | local Ollama |
| Scorer 1 | `openai/gpt-oss-120b` | Groq |
| Scorer 2 | `nex-agi/nex-n2.5-pro:free` | OpenRouter (Nex AGI) |
| Fabrication checker | `nvidia/nemotron-3-super-120b-a12b:free` | OpenRouter (NVIDIA) |

Four model families, none of them the generator's. How the second scorer and
the checker came to be these models is recorded in `PROTOCOL_DEVIATIONS.md`
(D2 to D5), each entry committed before the score it could influence.

## Why REJECT

Scorer 2 reported one critical fabrication in two answers; the checker
confirmed both. Scorer 1 reported none. Two votes for, none against: confirmed
under the majority rule (ADR-001 amendment).

Both answers claim that a blind handoff trial had already been run, while
their state said it was only proposed.

| Answer | Condition | Pair |
|---|---|---|
| `2d8d4d62…` | baseline (prose) | pair-405 |
| `02ebad79…` | structured (sections) | pair-408 |

**One fabrication in each condition.** The gate rejects the candidate because
the memory format did not prevent fabrication. It does not show that structure
causes fabrication: prose did it too, at the same rate.

## Quality scores (PCRB-1, out of 100)

Paired delta = structured minus baseline, same seed.

| | Scorer 1 (Groq) | Scorer 2 (Nex) |
|---|---|---|
| Mean, baseline | 95.0 | 88.8 |
| Mean, structured | 90.6 | 86.7 |
| Mean paired delta | −4.4 | −2.1 |
| Median paired delta | 0 | −1 |
| Pairs structured better / worse / equal | 0 / 4 / 5 | 3 / 5 / 1 |
| Two-sided sign test, ties dropped | p = 0.125 | p = 0.73 |

Per pair:

| Pair | Groq B | Groq S | Nex B | Nex S |
|---|---|---|---|---|
| 401 | 100 | 100 | 96 | 90 |
| 402 | 100 | 90 | 96 | 85 |
| 403 | 80 | 70 | 93 | 83 |
| 404 | 95 | 90 | 89 | 88 |
| 405 | 85 | 70 | 89 | 80 |
| 406 | 95 | 95 | 96 | 98 |
| 407 | 100 | 100 | 80 | 95 |
| 408 | 100 | 100 | 79 | 79 |
| 409 | 100 | 100 | 81 | 82 |

Where the structured condition lost points, both scorers put most of the loss
in `next_action_quality` (mean −2.8 and −2.1) and some in
`current_state_fidelity`.

The two scorers agree on direction (structured not better) and disagree on
individual pairs: pair 407 is equal for Groq and +15 for Nex.

## What this result can and cannot say

It can say: with this generator, these facts and this rubric, turning prose
into named sections did not help, and fabrication occurred in both formats.

It cannot say that structure harms handoff. Nine pairs, one small local
generator, and p-values of 0.125 and 0.73 do not support that claim.

## Limits

- **Ceiling effect.** Scorer 1 gave 100 to 9 of 18 answers. A rubric that
  saturates cannot measure improvement; the next rubric needs harder anchors.
- **One small generator.** A 3B model may not use structure at all. The
  question stays open for capable generators.
- **Batched scoring (D1).** Each scorer saw six answers per request, pairs kept
  together.
- **Replaced evaluators (D2–D5).** Two candidate scorers failed before
  producing an accepted scorecard: Gemma (rate limits), then Nemotron Super
  (arithmetic, twice). Nex's first answer was also refused for arithmetic; its
  second was accepted. All refused answers are archived under
  `results/api_evaluations/rejected_arithmetic/`.
- **Checker anchoring.** The checker was shown the allegation it tested.
- **Evaluator totals.** Totals were written by the evaluators and checked
  against their components; three of five scoring attempts failed that check.

## What changes because of this

1. Evaluators stop writing totals; the script adds components
   (`evaluation_policy.json`, `evaluator_writes_total: false`).
2. Fallback evaluators are pre-registered as an ordered ladder, so a failing
   model is replaced by protocol instead of by deviation.
3. The next experiment needs a rubric without a ceiling, more pairs, and a
   generator strong enough for format to matter. A fast API generator allows
   30 or more pairs in minutes; the local model becomes its own, separate
   question.
