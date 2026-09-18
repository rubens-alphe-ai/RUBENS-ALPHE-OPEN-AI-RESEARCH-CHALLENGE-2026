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
