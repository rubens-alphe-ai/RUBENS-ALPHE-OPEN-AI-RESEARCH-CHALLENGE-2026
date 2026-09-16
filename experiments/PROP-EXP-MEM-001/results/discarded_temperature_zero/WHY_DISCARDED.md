# Discarded run — temperature 0.0 collapsed the paired seeds

Executed 2026-09-16T04:44–04:51Z, `ollama` / `llama3.2:3b`, temperature 0.0,
seeds 101 / 202 / 303. Six files were produced and all six terminated
naturally, so the run looked successful.

It is not usable. Greedy decoding at temperature 0.0 ignores the seed, so the
seeds produced no independent sampling variation:

| Trial | output_sha256 |
|---|---|
| baseline-202 | `9378ddd3063879d1…` |
| baseline-303 | `9378ddd3063879d1…` ← byte-identical |
| structured-202 | `d236abf6880dccd2…` |
| structured-303 | `d236abf6880dccd2…` ← byte-identical |

Pairs 202 and 303 are exact duplicates of each other, not independent trials.
Pair 101 differs only because the model was cold on the first request, which is
an execution artifact rather than sampling variation.

Scoring this as three paired trials would manufacture false precision: the
95% lower confidence bound required by ADR-001 would be computed over
duplicated samples and would report a certainty the data does not contain.

`ADR-001` requires a lower confidence bound on paired deltas, and a bound
requires variance. Sampling variance therefore requires a temperature above
zero, held identical across both conditions. The rerun uses temperature 0.8
with the same three seeds and the same frozen protocol, prompt and state
hashes.

Kept as evidence of the design fault, per the project's policy of preserving
negative results.
