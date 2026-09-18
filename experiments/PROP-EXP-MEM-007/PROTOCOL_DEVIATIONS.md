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

## D3 — Output budget raised, and every handoff regenerated (2026-09-18)

**What happened:** with the reasoning effort set to minimal (D1), the model
still spends tokens before answering. Of 120 trials, 53 produced a handoff, 38
were cut at the 1,500-token budget and refused, and 29 returned reasoning with
no answer. The successful handoffs run from 366 to 432 words, right against the
450-word instruction, so the budget was binding on exactly the longest answers.

**Why this could bias the result:** a budget that only refuses the longest
answers does not drop trials at random. It drops whichever condition tends to
write more — and the checklist condition is the one asked to carry more facts.
Keeping those 53 handoffs would compare a complete baseline with a truncated
treatment, or the reverse.

**Deviation:** `max_output_tokens` goes from 1,500 to 3,000 and **all 120
trials are generated again from scratch**. The 53 earlier handoffs and the
error records are kept, unused, in `results/superseded_cap1500/`. Nothing else
changes: same model, same reasoning setting, same temperature, same seeds, same
states, same prompt, same 450-word instruction, same quiz, same key, same rule,
same ceiling. The guard first refused 4,000 tokens as over budget (0.54 USD against 0.50), so the budget is 3,000 tokens, about five times what a handoff uses.

**Decided before:** any handoff was read or graded. No reading had run.
