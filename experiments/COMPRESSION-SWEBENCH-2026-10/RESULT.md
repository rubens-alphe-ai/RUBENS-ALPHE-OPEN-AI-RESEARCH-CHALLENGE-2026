# Result: 40% of SWE-bench Verified ranks the next ten models as the whole does

Pre-registered in `PREREGISTRATION.md` (commit `d8698e2`, pushed before the
run). Reproduce with:

```
python scripts/compress_benchmark.py --table experiments/SWEBENCH-ITEMS-2026-10/swe_bench_verified.csv \
    --epoch-zip experiments/LEADERBOARD-REALITY-2026-10/epoch_benchmark_data_2026-10-03.zip \
    --benchmark swe_bench_verified --out result.json
```

**Split by release date.**
- **Training:** 20 models, from gpt-4o (2024-11) to glm-5 (2026-02-11).
- **Test:** 10 models released afterwards, from claude-sonnet-4-6
  (2026-02-17) to glm-5.2 (2026-06-16).
- The items were chosen with the training models only.

## All five predictions held

| Rule | Problems kept | Spearman on the 10 new models | Supported pairs keeping their order | Supported pairs no longer significant | Random subsets of the same size: median Spearman (5th percentile) |
|---|---|---|---|---|---|
| R1: drop problems every training model solved | 355 / 454 (78%) | 1.000 | 20 / 20 | 0 | 0.973 (0.906) |
| R2: drop problems the 10 best training models agree on | **183 / 454 (40%)** | **0.988** | **20 / 20** | 2 | **0.878 (0.689)** |

What this means:
- **R2 keeps 40% of the problems.** On ten models it never saw, it orders the
  models almost exactly as the full benchmark does.
- **Every ordering the full benchmark supports keeps its direction.** Two of
  those 20 orderings are no longer significant on the shorter set: that is
  the price of fewer items.
- **The choice of items matters.** A random 40% gives a median Spearman of
  0.878, and 1 in 20 random draws falls below 0.69. Selection beats plain
  sampling (C3).

## What it is worth

If problems cost alike, running R2 instead of the full set costs about 40% as
much, for the same ranking of new models. They do not cost exactly alike, so
the real saving has to be measured on a client's own run costs.

## Limits

- **One benchmark, ten test models.** A Spearman on ten models is coarse, and
  the 20 supported pairs are few.
- **The time horizon is four months** (February to June 2026). A selection
  ages: as models improve, problems that all the best models fail become
  informative again. The selection must be refreshed. That makes it a
  recurring service rather than a one-off file.
- **Contamination** affects every model alike and is not addressed here.
