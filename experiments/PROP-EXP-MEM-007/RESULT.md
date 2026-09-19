# PROP-EXP-MEM-007 — Result

**Decision: PROVISIONAL_KEEP**, decided 2026-09-19 under the rule frozen in
`PROTOCOL.md` (commit 3283e40, before the first trial).

With a DeepSeek writer — a third family — the handoff checklist again carries
more facts: **+5.5 points**, 95 % CI **+3.8 to +7.3**, with **no invented
facts** in either condition.

## Numbers

Sixty pairs, 120 handoffs, 120 readings, no missing trial.

| | Baseline (state only) | Checklist |
|---|---|---|
| Mean fact accuracy (32 questions) | 90.8 % | **96.3 %** |
| Inventions (10 absent questions × 60) | 0 of 600 | 0 of 600 |

- Mean paired delta: **+5.5 points**, 95 % CI +3.8 to +7.3
- Pairs: checklist better 46, worse 4, equal 10 — the most one-sided of the series
- Writer `deepseek/deepseek-v4.1-flash`; reader `openai/gpt-oss-120b`

This is the project's first experiment paid for rather than run on free quotas:
ceiling 0.50 USD written in the policy, priced before the first call, about
0.20 USD actually spent.

## What had to be fixed along the way

Recorded in `PROTOCOL_DEVIATIONS.md`, each before any score existed:

- **D1** — the writer reasons by default and returned six empty answers; its
  reasoning channel was switched off, as it is for the other writers in the
  series.
- **D3** — at 1,500 output tokens, 38 of 120 handoffs were cut and refused. The
  budget bound **only on the longest answers**, which is not a random way to
  lose trials: the condition asked to carry more facts writes more. Every trial
  was regenerated at 3,000 tokens and the 53 earlier handoffs were kept, unused,
  in `results/superseded_cap1500/`.
- **D5** — the reader ladder moved from one provider to another *serving the
  same model*, and the "never mix two readers" rule discarded 115 valid
  readings. The rule now triggers only when the model itself changes; the
  readings were restored, not re-taken.

None of these three would have produced an error in the final table. The first
would have lost runs, the second would have quietly favoured one condition, the
third would have wasted a day.

## Where this sits in the series

| Experiment | Writer | Reader | Delta | 95 % CI |
|---|---|---|---|---|
| MEM-005 | `qwen/qwen3.8-27b` | `openai/gpt-oss-120b` | +4.1 | +1.5 to +6.6 |
| MEM-006 | `moonshotai/kimi-k3` | `openai/gpt-oss-120b` | +5.9 | +3.5 to +8.2 |
| **MEM-007** | **`deepseek/deepseek-v4.1-flash`** | `openai/gpt-oss-120b` | **+5.5** | +3.8 to +7.3 |

## What this does not establish

- Same state and same quiz as MEM-004 to MEM-006; the holdout stays sealed.
- One reader model across the three experiments (an independent cross-read of
  MEM-006 by DeepSeek gave +5.1, consistent with it).
- Writer and reader were both served by OpenRouter here, so a gateway-wide fault
  would have hit both stages.
- The checklist and the quiz share an author.
