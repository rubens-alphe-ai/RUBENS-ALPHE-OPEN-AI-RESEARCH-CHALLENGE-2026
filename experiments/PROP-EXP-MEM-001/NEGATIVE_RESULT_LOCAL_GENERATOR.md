# Negative result — local `qwen3:4b` is not a viable generator for PROP-EXP-MEM-001

Measured: 2026-09-15/16. Recorded because this project preserves negative
results. No canonical state was changed. No trial output was written to
`results/`.

## Correction to the previously recorded cause

`CONTINUATION_STATUS.md` attributed the earlier failures to "the full project
context" being too large. Measurement does not support that.

The actual blind-trial prompt is **2 672 characters / 576 prompt tokens**
(`BASELINE_STATE.json` + `TEST_PROMPT.md`). Context size is not the
constraint. The constraints are generation throughput and unbounded
deliberation.

## Measurements

Host: Ollama `/api/ps` reports `size_vram: 0` — inference is **CPU-only**.

| # | Model | `think` | `num_predict` | Elapsed | `done_reason` | Answer chars | tok/s |
|---|---|---|---|---|---|---|---|
| 1 | `qwen3:4b-nothink` | n/a | 512 | 128.6 s | `length` | **0** | 3.98 |
| 2 | `qwen3:4b` | false | 1 400 | 349.8 s | `length` | 6 783 | 4.00 |
| 3 | `qwen3:4b` | false | 3 072 | 935.9 s | `length` | 14 333 | 3.28 |

Trial 1 returned an empty answer: the whole budget went to the reasoning
channel (`message.thinking`), leaving `message.content` empty. The
`qwen3:4b-nothink` variant built for this project does **not** disable
reasoning — it only hides it from `content`.

Trial 3 ran 15.6 minutes, emitted 14 333 characters, and **never terminated
naturally** (`TERMINATED_NATURALLY: False`). It was still deliberating about
the definition of PCRB-1 when the budget ran out. It never produced the five
required answers.

## Why this invalidates the experiment rather than merely slowing it

The generator must answer five questions and report a confidence value. This
model does not reach that structure within any budget tested. Both conditions
would therefore score at the floor, and a floor effect cannot discriminate
between `BASELINE` and `STRUCTURED_MEMORY_V1`.

Running the six trials anyway would cost roughly 94 minutes of wall clock and
produce six unusable transcripts. That is not evidence of a null effect; it is
absence of measurement. Recording it as a null result would be a fabrication.

## Consequence

`PROP-EXP-MEM-001` needs a generator that terminates. Per `ARCHITECTURE.md`
§6 the provider is replaceable and the benchmark stays provider-neutral, so
the frozen protocol, prompt and state hashes remain valid across this change;
only the generation block of the manifest changes.

The `qwen3:4b` arm is retained as a recorded capability limit of this host,
not as an experimental condition.
