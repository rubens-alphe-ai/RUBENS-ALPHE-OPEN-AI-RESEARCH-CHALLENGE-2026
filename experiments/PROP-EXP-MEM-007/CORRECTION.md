# PROP-EXP-MEM-007 — correction: the decision file does not follow from the stored answers

**Found 2026-09-19 by `scripts/regression_suite.py`, which was written to check
exactly this and found it on its first run.** The project has claimed, in every
result file and in five public posts, that every published verdict can be
recomputed from the stored answers. For this experiment that claim is false.

## What moved

Regrading all 120 stored reader records against the key rebuilt from `QUIZ.json`:

| Number | From the stored answers | Published in `results/decision.json` |
|---|---|---|
| `pairs_structured_better` | **46** | 45 |
| `pairs_equal` | **10** | 11 |
| `sd_delta_pp` | 6.9432 | 6.9907 |
| `ci95_delta_pp` | +3.712 to +7.226 | +3.700 to +7.238 |

## What did not move

`decision` (**PROVISIONAL_KEEP**), `reason_codes`, `pairs` (60),
`mean_paired_delta_pp` (**5.46875**) and `inventions` (0 and 0) are identical.
The verdict, the headline effect and the invention count are unaffected: one
pair moved from *equal* to *structured better* in a way that leaves the mean
exactly unchanged, which is what a single re-read of one trial looks like.

## What was established about it

- **All 120 per-record `grade` blocks reproduce exactly from their own stored
  `answers`.** The records are internally consistent; only the aggregate is not.
- **Every MEM-007 file still matches its hash in `SHA256SUMS.json`**, all 712
  covered entries including `decision.json`. Nothing was altered after
  publication. **The inconsistency was published, not introduced afterwards.**
- Every record's `read_at_utc` predates `decided_at_utc`, so this is not a late
  re-read that was never folded in.
- `RESULT.md` line 20 says "checklist better 46, worse 4, equal 10", and the
  registry note says "46 pairs better of 60". **The prose and the registry agree
  with the stored answers. The machine-readable decision file is the stale one.**
- It was invisible on the public page because `build_results_page.py` renders
  the interval to one decimal, where both versions read "+3.7 to +7.2".

## What is not being done about it

`results/decision.json` is **not** regenerated, and the stored answers are not
touched. Overwriting the file would remove the only evidence that the
discrepancy existed, and the hash record would then describe a file nobody
published. It stays as published, with this correction beside it, and
`tests/test_regression_suite.py` pins the mismatch by name so that it fails
loudly if anyone regenerates it without deciding to.

The numbers to cite are the ones from the stored answers, which are also the
ones in `RESULT.md`.

## The two claims that are not checkable at all

The same run found two published numbers that are not wrong but cannot be
verified, which for this project is a distinct and more serious category:

- **`results/decision-kimi-reader.json` in PROP-EXP-MEM-006** — a second,
  independent reading (+6.61 pp, CI +4.29 to +8.94, 60 pairs) by
  `reader-nvidia-kimi-k3`. **No directory of that reader's answers exists in the
  repository.** The summary survives; the evidence does not.
- **PROP-EXP-MEM-009**, all six merge directories — each `merge-NN.json` stores
  a `grade` but no `answers`, and there is no `answer-key.json`. Its headline
  recovery figures (+11.6, +6.9, +1.4) can be re-read but never regraded.

Both are recorded in the registry and reported by the suite as `unverifiable`,
which exits `2` — deliberately not the same as `mismatch`, and deliberately not
silence.

## What this changes going forward

The claim is narrowed to what is true: **8 of 11 published verdicts reproduce
exactly from the stored answers, 1 does not, and 2 rest on data that was never
stored.** `scripts/regression_suite.py` runs over the whole repository and says
which is which, so the claim no longer has to be taken on trust — including when
it is inconvenient.

Any future run must store the reader's answers, not only their grade. That is
the rule this correction adds.
