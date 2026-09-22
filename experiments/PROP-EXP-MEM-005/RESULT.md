# PROP-EXP-MEM-005 — Result


> **Effective length, measured 2026-09-22.** This quiz declares 32 fact questions and measures with about six: twenty-four are answered correctly by every reader in every trial. The effect below is real and its direction replicates, but it rests on a handful of items, and that is why a different reader moves its magnitude. See [docs/CORRECTIONS-2026-09-21.md](../../docs/CORRECTIONS-2026-09-21.md) and `scripts/item_analysis.py`.

**Decision: INCONCLUSIVE** (`CONFIDENCE_INTERVAL_SPANS_THRESHOLD`), decided
2026-09-18 under the rule frozen in `PROTOCOL.md` (commit 828dd6f, before the
first trial).

**The checklist works, but less than the project said would matter.** Adding a
short generic checklist after the state improved fact transfer by about four
points. The improvement is real — the confidence interval excludes zero — but
it does not reach the +5 points the protocol required, and the interval still
covers +5, so the rule refuses both a keep and a reject.

This is the first positive signal the project has produced.

## Numbers

Thirty pairs, sixty handoffs, sixty readings, no retry, no missing answer, no
deviation.

| | Baseline (state only) | Checklist |
|---|---|---|
| Mean fact accuracy (32 questions) | 87.6 % | **91.7 %** |
| Inventions (10 absent questions × 30) | 0 of 300 | 0 of 300 |
| Wrong facts asserted | 1 of 960 | 0 of 960 |

- Mean paired delta: **+4.1 points**
- 95 % confidence interval: **+1.5 to +6.6 points**
- Pairs: checklist better 19, worse 5, equal 6

## What the checklist changed

The gains land exactly where MEM-004 found the losses, without the checklist
naming any of them:

| Question | Baseline | Checklist |
|---|---|---|
| The founder's constraint (quota-limited, no continuous access) | 4 / 30 | **18 / 30** |
| The rule "an agent may propose, evaluation decides" | 5 / 30 | **12 / 30** |
| The project's name | 8 / 30 | 12 / 30 |
| Two rules in force | 23 / 30 | 26 / 30 |

Small losses appear elsewhere (the research theme 30 → 27, the failed digest
29 → 27): with a fixed length, carrying more of one kind of fact costs a little
of another. The net effect is positive.

Inventions stayed at zero in both conditions, so the improvement did not come
at the price of confident guessing.

## Reading the verdict honestly

- **Not a keep:** the pre-registered bar was +5 points, and the measured mean
  is +4.1. Lowering the bar after seeing the data would destroy what
  pre-registration is for.
- **Not a reject:** +5 is inside the interval, so an effect of that size is not
  excluded.
- **Not nothing:** the interval excludes 0, and 19 of 30 pairs improved. With
  the same effect size, roughly 60 pairs would separate it from +5 either way.

## Limits

- One generator (`qwen/qwen3.8-27b`), one reader (`openai/gpt-oss-120b`), one
  state, the same quiz as MEM-004. A second generator and a second reader are
  now possible (a third provider was added after this run) and are the next
  step.
- The checklist was written after MEM-004's results were known. It names only
  the state's own categories, and deliberately not the facts MEM-004 lost, but
  the design of the question set and of the checklist share an author.
- Reading again took 23.5 hours because the reader's daily quota on Groq was
  exhausted; this affects duration only, not the measurements.

## What comes next

1. **Replicate with a second generator and a second reader** (MEM-006). If the
   effect survives models from other families, it is a property of the
   checklist rather than of these two models.
2. **More pairs**, to decide between "below the bar" and "at the bar".
3. The sealed holdout state (`experiments/HOLDOUT-2026-09/`) stays unused until
   a candidate passes on this state.
