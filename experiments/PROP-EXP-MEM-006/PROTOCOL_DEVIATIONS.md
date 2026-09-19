# PROP-EXP-MEM-006 — protocol deviations

Each deviation is recorded and committed before any result it could influence
exists.

## D1 — Requests are sent several at a time (2026-09-18)

**What changed:** the runner sent one request at a time; it now sends several in
parallel (generation six at a time, reading four at a time).

**Why it changes nothing measured:** each trial is a stateless request that
shares nothing with the others — same model, same prompt, same settings, same
seed, same order of questions, same grading. A unit test checks that the same
trials produce byte-identical outputs run in parallel or one by one, and that
resuming never regenerates an existing output.

**What it changes:** the series takes hours instead of a day.

**Decided before:** any verdict. Trials already produced are kept untouched and
were generated one at a time; the rest are generated in parallel.

**Second amendment to D1 (before any reading was graded):** the first reader
kept returning gateway timeouts even one request at a time, after having
answered a single probe minutes earlier. Waiting for 120 trials to exhaust
their retries before the ladder moves on would take about eighteen hours, so
the runner now declares a reader unable after five failed trials and hands the
whole reading to the next rung, which is what the ladder was written for.

## D3 — The second reader was the generator itself; every handoff is read again (2026-09-19)

**What happened:** the pre-registered ladder's first reader (`z-ai/glm-5.3`)
failed and was replaced by its second rung, `moonshotai/kimi-k3` — which is the
model that wrote every handoff in this experiment. It read all 120 and the
adjudicator recorded PROVISIONAL_KEEP: +6.6 points, 95 % CI +4.3 to +8.9, zero
inventions in either condition.

**Why that verdict is not kept as it stands:** a model reading its own writing
is not an independent reader. It may recover its own phrasing, conventions and
abbreviations better than another model would, which would inflate the measured
difference. The ladder was written without checking that a rung could collide
with the generator; that is a design fault in this experiment, not a property of
the models.

**Deviation:** the Kimi reading is set aside in
`results/quiz/abandoned/reader-nvidia-kimi-k3/` with its decision preserved as
`decision-kimi-reader.json`, both published. The same 120 frozen handoffs are
read again by the ladder's third rung, `openai/gpt-oss-120b` on Groq, which
shares no family with the generator. The verdict of record is the one produced
by that independent reader, whatever it says.

**Decided before:** the independent reading began. The Kimi verdict is public so
the difference between the two readers can be compared afterwards — that
comparison is exploratory, not part of the decision.

**Amendment to D4 (before the verdict):** one handoff of 430 words made the
reader spend its whole 2,000-token budget reasoning and return nothing. Its
budget is 5,000 tokens. The prompt, the model, the key and the rule are
unchanged; this only lets the reader finish an answer it had started.
