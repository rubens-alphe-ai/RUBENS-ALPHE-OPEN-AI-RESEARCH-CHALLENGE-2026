# PROP-EXP-MEM-014 — deviations

## D1 — the first batch is unusable, and I saw its scores before I knew why

**Recorded 2026-09-19, after the scores were seen. That is a departure from this
project's own rule and is stated first rather than buried.**

### What happened

The first batch produced **6 failed runs of 24**, distributed `summary` 2,
`checklist` 2, `sections` 2, `facts_only` **0**. The registered failure rule is
that failures falling unevenly across conditions by more than 10 % of runs make
an experiment **unusable rather than analysable**. A two-run gap on arms of six
is a 33-point difference in failure rate. **The batch is unusable.** Its numbers
are not analysed here and are not the result of this experiment.

### The cause, which is a harness fault and not a property of generated prose

Five of the six failures are the reader's answer truncated at
`max_output_tokens=2000`; the sixth is the reader returning only reasoning.

MEM-008 — the run this experiment was registered to reproduce *unchanged* — gave
its reader **5000** tokens in `evaluation_policy.json`. `scripts/handoff_bench.py`
hard-codes the reader at **2000** and exposes no flag for it, so invoking the
benchmark from the command line silently gave the reader less than half the
budget the comparison run had. I did not notice, because there was nothing to
notice: the number is not in the policy the script reads and not on the command
line.

The protocol said "nothing about the harness is adapted for a generated
document; that is the point." It was adapted, by me, by omission.

### The order in which this was found, stated plainly

I looked at the scores first, saw the failure count second, and identified the
cause third. The rule requires a deviation to be recorded before any score it
could influence is seen, and that did not happen.

What this does and does not compromise:

- **It does not let a threshold move.** The decision rule is three numeric
  conditions fixed in `PROTOCOL.md` before the run, and they are unchanged.
- **It does compromise the independence of the decision to rerun.** I knew the
  direction of the numbers when I decided the batch was faulty. The defence is
  that the fault is verifiable without reference to any score — 2000 against
  5000, in two files, and five failures naming truncation explicitly — and that
  anyone would call it a deviation. That defence is offered, not assumed.

### What is being done

1. `scripts/handoff_bench.py` gains a `--reader-max-tokens` flag, defaulting to
   the 5000 MEM-008 used. A budget that cannot be set from the place a run is
   launched is a fault waiting to repeat.
2. The unusable batch is kept at `results/superseded_reader2000/` rather than
   deleted, with this file, so the failure and its cause stay readable.
3. The experiment is rerun in full with the reader budget MEM-008 had. The three
   registered conditions are applied to the rerun and to nothing else.

If the rerun also fails unevenly, the experiment is reported as unusable and the
bridge is left untested rather than argued.
