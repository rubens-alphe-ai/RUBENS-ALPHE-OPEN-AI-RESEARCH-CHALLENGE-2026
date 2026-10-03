# Result: on MedQA, half the items rank the next ten models as the whole does

Pre-registered in `PREREGISTRATION.md` (commit `1a52ba5`, pushed before the
run). Reproduce with:

```
python scripts/compress_benchmark.py --table experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa.csv \
    --dates-json experiments/COMPRESSION-MEDQA-2026-10/helm_release_dates.json --window 30 \
    --benchmark med_qa --out result.json
```

**The split.**
- **Test models (released last):** llama-3.2-90b, claude-3.5-sonnet
  (2024-10-22), claude-3.5-haiku, solar-pro, nova-lite, nova-micro, nova-pro,
  llama-3.3-70b, gemini-2.0-flash-exp and deepseek-v3.
- **Training models:** the 20 released before them.

## All five predictions held, and the third only just

| Rule | Items kept | Spearman on the 10 new models | Supported pairs keeping their order | Supported pairs no longer significant | Random subsets of the same size: median (5th percentile) |
|---|---|---|---|---|---|
| R1 | 925 / 1,000 | 1.000 | 36 / 36 | 0 | 0.997 (0.988) |
| R2 | **498 / 1,000 (50%)** | **0.985** | **36 / 36** | 1 | **0.982 (0.948)** |

## Two benchmarks together

| | SWE-bench Verified | MedQA |
|---|---|---|
| Kept by R2 | 40% | 50% |
| Spearman on new models | 0.988 | 0.985 |
| Supported orders kept | 20 / 20 | 36 / 36 |
| Random subset, same size (median) | 0.878 | 0.982 |

**What holds on both benchmarks:** about half of the items, or fewer, rank
the models released afterwards as the full benchmark does, and every
supported order keeps its direction.

**What differs:**
- **On SWE-bench, the choice of items matters a lot.** A random 40% is
  clearly worse.
- **On MedQA, it hardly matters.** With 1,000 items, a random half already
  ranks almost as well, and R2 beats it only by 0.003 of median Spearman.

So the saving comes mostly from running fewer items. The added value of
choosing them is large on agentic benchmarks with many items that every
leading model passes, and small on a large multiple-choice set.

## What may be said

| Claim | May it be said? |
|---|---|
| On two public benchmarks of different kinds, about half the items, chosen on earlier models, ranked later models as the full set did | Yes |
| Choosing the items beats random sampling on SWE-bench | Yes |
| Choosing the items beats random sampling on MedQA | Not meaningfully |
| A given saving for a client | No, until it has been measured on that client's own costs and held-out models |

## Limits

- **Ten test models each, and short horizons.** Four months on SWE-bench and
  three on MedQA.
- **MedQA's test models date from late 2024.** HELM lite v1.13.0 has none
  more recent.
- **One tie straddles the split** (llama-3.2-11b and llama-3.2-90b), as
  declared in advance.
