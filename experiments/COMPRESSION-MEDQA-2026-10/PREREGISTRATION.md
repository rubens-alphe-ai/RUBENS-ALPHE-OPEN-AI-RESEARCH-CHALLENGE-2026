# Pre-registration: the compression test, repeated on a second benchmark (MedQA)

Written 2026-10-03T19:11:23Z (clock). Committed and pushed before the
compression script is run on these data.

## Why

COMPRESSION-SWEBENCH-2026-10 held on one benchmark. One benchmark is not a
product claim. This repeats the same rules, unchanged, on a benchmark of
another kind: 1,000 multiple-choice medical questions rather than 454 coding
tasks, and models from another period.

Epoch AI's public logs could not serve. Most older logs answered HTTP 403.
Only 10 models were readable for GPQA Diamond, none for SimpleQA Verified,
and 20 models on 46 items for chess puzzles: too few for a 20/10 split.

## Data

- **Answers.** `experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa.csv`: HELM
  lite v1.13.0, 91 models × 1,000 items, exact match (already public; audited
  in PUBLIC-AUDIT-2026-10).
- **Release dates.** HELM's own `schema.json` for that release (sha256
  `3ac5baab…2fe5`), saved as `helm_release_dates.json`. It has a date for all
  91 models.
- **Window.** The 30 most recent models (`--window 30`). Ordered by date, ties
  broken by name:
  - the 20 earliest are the training models (2024-05-24 to 2024-09-25);
  - the 10 latest are the test models (2024-09-25 to 2024-12-24).

**One tie straddles the split:** `llama-3.2-11b` (training) and
`llama-3.2-90b` (test) share 2024-09-25. This is declared here and not
changed.

## What is already known

Known to the author, from PUBLIC-AUDIT-2026-10: among the top 20 of all 91
models, 204 of the 1,000 items carry information. Nothing is known yet about
the split, the rules' subsets or their performance on the test models.

## Rules, predictions and script

The same as COMPRESSION-SWEBENCH-2026-10, with the same thresholds, by
`scripts/compress_benchmark.py` (sha256 `2199ae76…` at this commit; the only
changes since that study are the `--dates-json` and `--window` options, and
it reproduces the SWE-bench result exactly).

| ID | Prediction |
|---|---|
| C1 | Spearman, full against subset, on the 10 test models ≥ 0.90, for R1 and for R2 |
| C2 | ≥ 95% of the test pairs supported on the full set keep the same order on the subset, for R1 and for R2 |
| C3 | R2's Spearman is at least the median Spearman of random subsets of its size |

## How the result will be used

- **If C1 to C3 hold on MedQA as on SWE-bench,** the site and the brief may
  say that the method has held on two benchmarks of different kinds.
- **If any prediction fails,** the offer stays, but it is described as tested
  on one benchmark only, and each client's selection is checked on that
  client's own held-out models before delivery.
