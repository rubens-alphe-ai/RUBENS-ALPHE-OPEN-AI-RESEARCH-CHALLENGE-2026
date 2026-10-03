# What the top of today's leaderboards actually supports

Epoch AI publishes, for every model it runs on each benchmark, a score **and the
standard error of that score**. The error bars are on the page. What nobody
prints is what they imply for the order of the models at the top — the order
people choose models by.

This reads Epoch's own numbers and says it. Nothing here is re-measured; every
score and every error is Epoch's.

**Source and licence.** Epoch AI, *Capabilities & benchmarking*,
https://epoch.ai/benchmarks, retrieved 2026-10-03 as `benchmark_data.zip`
(sha256 `5e7acc5b…683b8c5`, archived beside this file). Data published under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). This analysis is ours,
not Epoch's, and is not endorsed by them.

Reproduce with:

    python scripts/leaderboard_reality.py --zip experiments/LEADERBOARD-REALITY-2026-10/epoch_benchmark_data_2026-10-03.zip --out result.json

## The finding

Thirteen benchmarks have at least ten distinct models with a published error.

- **On all thirteen, none of the nine neighbouring orderings in the top ten is
  supported** by the published errors at 95%.
- **On ten of the thirteen, the first model cannot be separated from the
  fifth.**
- **On two, the first cannot be separated from the tenth.** On GPQA Diamond the
  top ten sit within 1.8 points, and 25 distinct models are statistically tied
  with the leader. On the mock AIME set, 16 entries score 100% and the top ten
  span exactly nothing.

| Benchmark | Distinct models | Leader | Leader % | Tied with leader | Top-10 neighbouring orderings unsupported | 1st separated from 5th | 1st separated from 10th | Top-10 span (pts) |
|---|---|---|---|---|---|---|---|---|
| otis_mock_aime_2024_2025 | 197 | gpt-6.1-sol_max | 100.0 | 37 | 9 of 9 | **no** | **no** | 0.0 |
| gpqa_diamond | 219 | gpt-6-astra_max | 95.8 | 25 | 9 of 9 | **no** | **no** | 1.8 |
| frontiermath_tier_4 | 56 | gdm-ai-co-mathematician | 47.9 | 5 | 9 of 9 | **no** | yes | 29.1 |
| frontiermath_tiers_1_3_v2 | 81 | gpt-6.1-sol_max | 93.7 | 5 | 9 of 9 | **no** | yes | 7.7 |
| math_level_5 | 97 | gpt-5-2025-08-07_high | 98.1 | 5 | 9 of 9 | **no** | yes | 2.2 |
| chess_puzzles | 141 | gpt-6-astra_max | 72.0 | 4 | 9 of 9 | **no** | yes | 18.0 |
| frontiermath | 71 | gpt-5.5-pro-pre-release_high | 52.4 | 4 | 9 of 9 | **no** | yes | 13.4 |
| furniture_assembly | 29 | claude-opus-5-5_max | 83.3 | 4 | 9 of 9 | **no** | yes | 39.2 |
| swe_bench_verified | 32 | claude-opus-4-7_max | 83.5 | 4 | 9 of 9 | **no** | yes | 6.8 |
| frontiermath_tier_4_v2 | 64 | gpt-6.1-sol_max | 100.0 | 3 | 9 of 9 | **no** | yes | 22.0 |
| simpleqa_verified | 77 | gpt-6-astra_max | 75.6 | 3 | 9 of 9 | yes | yes | 8.8 |
| ebr_bench | 11 | gpt-6-astra_max | 76.2 | 2 | 9 of 9 | yes | yes | 45.7 |
| mystery_game_puzzles | 73 | gpt-6-astra_max | 84.0 | 1 | 9 of 9 | yes | yes | 32.0 |

A wide span does not rescue the order. FrontierMath Tier 4 spreads its top ten
over 29 points and still cannot separate first from fifth: it has few problems,
so each score carries a large error.

## What it means

**A frontier leaderboard today is a tier, not a ranking.** It can say which
models are in the leading group. On every benchmark here, it cannot say which
of two neighbours inside that group is better, and on most it cannot say whether
the first is better than the fifth.

So a choice between the top few models, made because one prints above another,
is not made on a measurement. It may still be the right choice — on price,
latency, licence, or on the buyer's own tasks. Those are the things that should
decide it, and a private evaluation built for the decision is how to measure the
last of them.

## Choices made, and why

- **One entry per model.** Epoch lists one model under several reasoning
  settings. Two settings of one model are expected to sit side by side, and
  counting them as neighbours would inflate every unsupported ordering. Each
  model is kept once, at its best setting. Without this the result is the same
  in direction and stronger in size.
- **Identical scores separate nobody.** Sixteen entries sit at 100% on the mock
  AIME set with a published error of zero. A rule that compares a difference of
  zero against an error of zero would call their order supported; it is
  counted as unsupported.
- **Conservative where it matters.** The comparison is unpaired: a paired test
  on per-item results would separate some pairs this cannot. No correction is
  applied for comparing many pairs, which would separate fewer, not more. The
  two choices pull in opposite directions; neither is tuned.
- **Epoch's errors as published.** They are not re-estimated. Where an error is
  understated — a score at exactly 100% with an error of zero is the clearest
  case — the real uncertainty is larger than shown.

## What it does not say

- It does not say any benchmark is badly built. Models at the frontier may
  simply be that close.
- It does not say Epoch presents anything wrongly. Epoch publishes the error
  bars; this reads them into orderings.
- It says nothing about which items in each benchmark carry the measurement.
  That needs per-item results — see the SWE-bench Verified item analysis when
  it lands, from Epoch's own public logs.
