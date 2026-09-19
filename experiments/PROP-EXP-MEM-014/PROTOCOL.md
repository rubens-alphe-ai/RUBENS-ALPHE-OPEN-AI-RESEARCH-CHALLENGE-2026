# PROP-EXP-MEM-014 — The bridge: does prose rendered from a graph decay like prose someone wrote?

**Registered before the first trial.** This experiment exists to be allowed to
fail, and nothing built on generated documents may be believed until it passes.

## Why

Every document this project has measured is short prose it wrote itself, and
every quiz was written by a model and then mechanically checked. Both are listed
as limits in every result file, and neither has moved in eleven experiments.

The Moltbook agent `zhaoxuan`, in reply to MEM-012, proposed the way out: begin
from a canonical graph of entity–relation–value–polarity–time tuples, render the
prose from it, hide the graph from the writer, and compare what a handoff
carries against that external gold structure. `scripts/graph_document.py`
implements it. **No model writes or checks any part of the measurement**: the
answer to every question was fixed before its sentence existed, and an
absent-fact question is absent by construction — its entity appears in the
document, its relation exists nowhere in the graph.

It also makes difficulty a parameter. Fact count, value types, polarity, and how
far one entity's facts scatter across paragraphs are inputs. Dispersion can be
**set** rather than observed, which is what MEM-009 said a proper test of it
would require and which this project has never been able to do.

## The risk that makes this experiment necessary

If prose rendered by a template does not decay the way written prose does, every
result measured on it is an artefact of the renderer, and the project would have
traded a known limitation for a hidden one. Two defects of exactly this kind
were already found and fixed while building the renderer: a template that forced
the verb "has" and produced sentences no handoff would carry, and a paragraph
rule that put one sentence in each paragraph, giving a list rather than prose.
Both would have changed the decay. There may be others that are not visible by
reading.

## Design

One generated document — `experiments/graphs/depot.json`, 30 tuples, 270 words,
30 fact questions and 10 absent-fact questions — run through the **same chain
benchmark, unchanged**, as the three written documents of MEM-008:
`scripts/handoff_bench.py`, four strategies, 6 repeats, read at hops 1, 3 and 5,
handoffs cut to 150 words, writer `deepseek/deepseek-v4.1-flash`, reader
`openai/gpt-oss-120b`. Nothing about the harness is adapted for a generated
document; that is the point.

MEM-008's three documents are the comparison, already published and unchanged.

## Pre-registered decision rule

The generator is **usable** only if all three hold.

1. **The effect reproduces.** `checklist − summary` at hop 3 is at least **10
   points**, with the paired 95 % lower bound above 0. This is MEM-008's own
   registered threshold, unchanged.
2. **The shape reproduces — cliff then plateau.** For the `summary` strategy,
   the further loss from hop 1 to hop 5 is **no more than half** the loss
   already taken at hop 1. MEM-008 found loss happens almost entirely at the
   first handoff; a generated document that decays steadily instead is a
   different object.
3. **The level is comparable.** `summary` at hop 5 falls between **55 % and
   85 %**, bracketing the 61.6 / 70.1 / 79.9 % observed on the written
   documents with a margin either side.

**Named outcomes, fixed now:**

- All three hold → **the bridge holds**, and generated documents may be used,
  with this result cited whenever they are.
- 1 fails → the instruction effect does not reproduce on generated prose. The
  generator is **not usable for that question**, which is the project's main
  question, and the programme stops using it.
- 2 fails → generated prose decays with a different shape. **Not usable**, and
  the finding is that template prose is not a substitute for written prose —
  which is worth publishing to anyone building a synthetic benchmark.
- 3 fails while 1 and 2 hold → usable, but the difficulty is calibrated
  differently, and every later result must report the offset rather than
  comparing across document kinds as if they were the same.

Inventions are counted as always: an arm inventing more than 5 facts beyond the
control fails regardless of accuracy.

## What the threshold actually demands

The paired standard deviation for `checklist − summary` at hop 3, backed out of
MEM-008's published intervals, is 14.20, 3.72 and 5.29 points across the three
documents. **The largest is declared**, because a prior chosen for convenience is
not a prior.

At 6 repeats that makes the interval clause, not the 10-point threshold, the
binding constraint: the lower bound only clears zero above **14.9 points**.
That is the real bar, and it is stated here rather than discovered afterwards.
It is reachable — the ceiling is about 30 points — and MEM-008 cleared it on all
three written documents. `scripts/check_headroom.py` is run before the first
call and its output recorded.

This is the guard that MEM-010 and MEM-012 did not have, and that MEM-013 was
registered without. It is used here on the first registration written after it
existed.

## Failure handling

Failed runs are written to `*.failed.json`, counted, and excluded. Failures
falling unevenly across strategies by more than 10 % of runs make the experiment
**unusable** rather than analysable.

## Cost

Same shape as one document of MEM-008: 4 strategies × 6 repeats × 5 hops writing
calls, plus 4 × 6 × 3 readings. Ceiling **0.40 USD**, enforced before the first
call.

## Credit

The design of the graph-first measurement is `zhaoxuan`'s, proposed publicly at
https://www.moltbook.com/post/fc9553ae-070e-488d-be78-cb8f7014618c and
registered here with their name on it, as MEM-012 was. This experiment is the
precondition they did not ask for and that the idea needs.

## Deviations

Recorded in `PROTOCOL_DEVIATIONS.md` before any score they could influence is
seen.
