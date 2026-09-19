# PROP-EXP-MEM-006 — Result

**Decision: PROVISIONAL_KEEP**, decided 2026-09-19 under the rule frozen in
`PROTOCOL.md` (commit e338d1a, before the first trial).

The handoff checklist of MEM-005 replicates with a different generator and a
different reader: **+5.9 points** of fact transfer, 95 % CI **+3.5 to +8.2**,
above the +5 bar set in advance, with **no invented facts** in either condition.

## Numbers

Sixty pairs, 120 handoffs, 120 readings, no missing trial.

| | Baseline (state only) | Checklist |
|---|---|---|
| Mean fact accuracy (32 questions) | 89.0 % | **94.9 %** |
| Inventions (10 absent questions × 60) | 0 of 600 | 0 of 600 |

- Mean paired delta: **+5.9 points**, 95 % CI +3.5 to +8.2
- Pairs: checklist better 39, worse 12, equal 9
- Generator `moonshotai/kimi-k3`; reader `openai/gpt-oss-120b`, no shared family

## The reader problem, and what was done about it

The pre-registered reader (`z-ai/glm-5.3`) answered one probe and then returned
gateway timeouts on every request, at four, two and one at a time. The ladder's
next rung was `moonshotai/kimi-k3` — **the model that wrote every handoff**.

It read all 120 and produced +6.6 points (CI +4.3 to +8.9). That verdict is kept
as `results/decision-kimi-reader.json` but is **not** the result of record: a
model reading its own writing may recover its own phrasing better than a
stranger would, which would inflate the difference. The ladder had been written
without checking that a rung could collide with the generator — a design fault,
recorded as deviation D3.

The same 120 frozen handoffs were then read again, twice, by readers sharing no
family with the generator:

| Reader | Delta | 95 % CI | Status |
|---|---|---|---|
| `moonshotai/kimi-k3` (wrote the handoffs) | +6.6 | +4.3 to +8.9 | set aside, published |
| `openai/gpt-oss-120b` | **+5.9** | +3.5 to +8.2 | **result of record** |
| `deepseek/deepseek-v4.1-flash` | +5.1 | +3.0 to +7.1 | exploratory cross-read |

**The effect barely moves when the self-reading is removed**, and two unrelated
readers land within one point of each other. What is measured is what the
handoff carries, not who reads it.

## Where this sits in the series

| Experiment | Writer | Reader | Delta | 95 % CI |
|---|---|---|---|---|
| MEM-005 | `qwen/qwen3.8-27b` | `openai/gpt-oss-120b` | +4.1 | +1.5 to +6.6 |
| **MEM-006** | `moonshotai/kimi-k3` | `openai/gpt-oss-120b` | **+5.9** | +3.5 to +8.2 |
| MEM-007 | `deepseek/deepseek-v4.1-flash` | `openai/gpt-oss-120b` | +5.5 | +3.8 to +7.3 |

Three writer families, the same instruction, the same quiz, the same threshold
fixed before any of them ran. Every interval excludes zero; not one invented
fact anywhere.

## What this does not establish

- One state and one quiz throughout. The sealed holdout
  (`experiments/HOLDOUT-2026-09/`) has not been touched.
- The checklist was written by the same assistant as the quiz, after MEM-004.
- `FINAL_KEEP` still needs calibration that passes and a regression suite;
  calibration failed once and has not been rerun.
- Reading was interrupted repeatedly by provider failures. Everything that was
  set aside is published, so the path from those failures to this number can be
  audited: see `PROTOCOL_DEVIATIONS.md` D1 to D4.
