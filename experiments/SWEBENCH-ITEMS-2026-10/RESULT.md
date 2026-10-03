# SWE-bench Verified, item by item: what the ranking of coding models rests on

SWE-bench Verified is the coding benchmark most often quoted when a model is
launched. Epoch AI runs it on frontier models and links a public Inspect log to
most runs (data under CC BY 4.0). This reads the per-problem results out of
those logs and asks which problems actually separate the models.

**Source.** Epoch AI, *Capabilities & benchmarking*, https://epoch.ai/benchmarks,
benchmark `swe_bench_verified`, logs linked from the CSV archived in
`experiments/LEADERBOARD-REALITY-2026-10/`. Every log read is listed, with the
sha256 of what was read, in
[`swe_bench_verified.provenance.json`](swe_bench_verified.provenance.json).
The analysis is ours, not Epoch's.

Reproduce with:

    python scripts/import_epoch_inspect.py --epoch-zip experiments/LEADERBOARD-REALITY-2026-10/epoch_benchmark_data_2026-10-03.zip \
        --benchmark swe_bench_verified --out swe.csv --manifest swe.provenance.json
    python scripts/item_analysis.py --table swe.csv

(Some logs are zstd-compressed; reading them needs `pip install zstandard`.)

## What was read

- **30 models.** Two linked logs answered 403 and are excluded by name in the
  provenance file.
- **454 problems** scored for every one of the 30. Epoch's runs score 484
  problems; a problem missing a score for any model — an errored run — is
  dropped from the table rather than counted as a failure.
- Only each log's `summaries.json` was read, by HTTP range request: a few
  megabytes per model instead of logs that reach several gigabytes.

## The finding

These are counts, not estimates. They need no statistics to believe.

| Panel | Solved by every model | Solved by none | Problems that give every model the same result |
|---|---|---|---|
| All 30 models | 95 | 35 | 130 of 454 (29%) |
| **The 15 leading models** | **230** | **39** | **269 of 454 (59%)** |
| The 10 leading models | 257 | 39 | 296 of 454 (65%) |

**Among the fifteen leading coding models, 269 of the 454 problems give every
one of them the same result.** Those problems add the same amount to every
score and cannot change the order. The ranking of frontier coding models on
this benchmark rests on fewer than half its problems.

The item analysis puts it in its own terms: across the 30 models, *a test of
454 items that measures with 218*; across the leading 15, with 65. At fifteen
respondents that second figure is a rough one — our own characterisation shows
effective length is understated on small panels — so the exact counts above are
the figures to quote.

**No problem runs backwards on the strict list.** Twenty do on the screening
list, which at thirty respondents flags roughly one healthy item in seven by
itself. So nothing here suggests a broken test, and nothing is claimed about
one.

## What it does and does not say

- It does not say SWE-bench Verified is badly built. A problem every frontier
  model now solves was hard when the benchmark was made. It says the benchmark
  is saturating at the top, and which problems are doing the separating.
- **The 39 problems no leading model solves are worth a look, not a verdict.**
  They are either genuinely beyond current models or not solvable as posed.
  Telling which takes a person reading each one, and that has not been done
  here.
- The panel is the set of models Epoch ran with a public log — not chosen by
  us, and not random.

## Found on the way: two defects in our own adapter

Reading these logs exposed two failures in `scripts/from_harness.py`, the tool
the site says reads Inspect logs directly:

1. **Newer Inspect logs are zstd-compressed**, which Python's standard library
   cannot read. Half of these logs failed with "That compression method is not
   supported". The adapter now reads them when the `zstandard` package is
   installed, and otherwise refuses with the fix named.
2. **Agent logs are huge.** Loading every transcript of a 1.1 GB log ran out of
   memory. The adapter now reads the per-sample summaries when every one is
   scored — 3.5 MB for that log — and falls back to the samples otherwise.

Both would have been found by the first client with a recent agent benchmark.
