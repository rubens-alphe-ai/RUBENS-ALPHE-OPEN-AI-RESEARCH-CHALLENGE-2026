# PROP-EXP-MEM-007 — protocol deviations

Each deviation is recorded and committed before any result it could influence
exists.

## D1 — The generator's reasoning channel is switched off (2026-09-18)

**Pre-registered:** `deepseek/deepseek-v4.1-flash`, temperature 0.8, at most
1,500 output tokens.

**What happened:** every one of the first requests failed the same way. The
model spent its whole output budget on an internal reasoning trace and returned
an empty answer, so the runner refused it, as it refuses any truncated or empty
generation. Six trials errored and **not one handoff was produced**; the run was
stopped.

**Cause:** this model reasons by default through OpenRouter. The adapter counts
only `message.content`, which stayed empty.

**Probe, on neutral text (a bakery, no experiment content):** with
`reasoning: {"enabled": false}` the model answered in 58 s with 376 words; with
`reasoning: {"effort": "minimal"}` in 8 s with 298 words. Both are inside the
budget and the word limit.

**Deviation:** the generation request adds
`extra_body: {"reasoning": {"effort": "minimal"}}`. Nothing else changes: same
states, same prompt, same temperature, same seeds, same quiz, same key, same
decision rule, same ceiling. The other generators in this series (Qwen, Kimi)
were likewise run without a reasoning channel, so this aligns MEM-007 with them
rather than departing from them.

**Decided before:** any handoff existed. The six error records are kept in
`results/` as `*.error.json`.

## D2 — Requests are sent several at a time (2026-09-18)

**What changed:** the runner sent one request at a time; it now sends several in
parallel (generation eight at a time, reading six at a time).

**Why it changes nothing measured:** each trial is a stateless request that
shares nothing with the others — same model, same prompt, same settings, same
seed, same order of questions, same grading. A unit test checks that the same
trials produce byte-identical outputs run in parallel or one by one, and that
resuming never regenerates an existing output.

**What it changes:** the series takes hours instead of a day.

**Decided before:** any verdict. Trials already produced are kept untouched and
were generated one at a time; the rest are generated in parallel.
