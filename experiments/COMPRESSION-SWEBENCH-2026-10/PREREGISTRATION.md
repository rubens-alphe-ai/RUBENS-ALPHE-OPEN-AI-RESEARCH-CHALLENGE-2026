# Pre-registration: a shorter SWE-bench Verified that still ranks new models the same way

Written 2026-10-03T18:45:43Z (clock), before the selection rules were applied
to the data. Committed and pushed before the script is run.

## Why

Agentic benchmarks are expensive to run: each item is a long run of a model
with tools. In SWE-BENCH-ITEMS-2026-10, 269 of the 454 problems gave every one
of the 15 leading models the same result. Those counts are already public and
known to the author of this file. The selection rules below are fixed without
knowing how they perform on the held-out models.

If items chosen with the models of the past keep ranking the models of the
future, a client can run a fraction of the benchmark and take the same
decisions. That is a saving, and it is measurable.

## Design (`scripts/compress_benchmark.py`, sha256 `4e70df96…` at this commit)

- **Data.** `experiments/SWEBENCH-ITEMS-2026-10/swe_bench_verified.csv`: 30
  models × 454 problems, from Epoch AI's public logs.
- **Split by release date** (Epoch AI's column, ties broken by name). The 20
  earliest models are the **training** models; the 10 latest are the **test**
  models. Every test model was released after every training model; the
  earliest test model is `claude-sonnet-4-6`, released 2026-02-17.
- **Rules, applied to training models only.**
  - R1 drops the problems every training model solved.
  - R2 drops the problems on which the 10 best training models (by full score)
    all agree.
- **Evaluation on the 10 test models.** For each rule:
  - the Spearman correlation between scores on the full set and on the subset;
  - for every pair of test models whose order is supported on the full set
    (exact McNemar, p < 0.05), whether the subset gives the same order.
- **Random baseline.** 1,000 random subsets of the same size, drawn with
  `random.Random(20261003)`.

## Predictions

| ID | Prediction |
|---|---|
| C1 | Spearman, full against subset, on the test models ≥ 0.90, for R1 and for R2 |
| C2 | ≥ 95% of the test pairs supported on the full set keep the same order on the subset, for R1 and for R2 |
| C3 | R2's Spearman is at least the median Spearman of random subsets of its size |

## Reported, not predicted

- **Cost.** The share of problems kept, which is roughly the share of the
  run's cost if problems cost alike. They do not, exactly.
- **Power lost.** How many supported pairs are no longer significant on the
  subset: fewer items mean wider intervals.

## What each outcome would mean

| Outcome | Meaning |
|---|---|
| C1 and C2 hold for R2, and C3 holds | A "compressed benchmark" can be offered: same decisions, a measured fraction of the cost. The choice of items adds value over plain sampling. |
| C1 and C2 hold, but C3 fails | Fewer items suffice, but choosing them adds nothing over random sampling, so nothing specific can be sold. |
| C1 or C2 fail | Items chosen on past models do not carry over to new models. No compression product. |

## Limits stated in advance

- **One benchmark, 10 test models.** A Spearman on 10 models is coarse.
- **Equal cost per problem** is an approximation.
- **The test models are recent, but the benchmark is not new:** problems can
  be contaminated for all models alike.
