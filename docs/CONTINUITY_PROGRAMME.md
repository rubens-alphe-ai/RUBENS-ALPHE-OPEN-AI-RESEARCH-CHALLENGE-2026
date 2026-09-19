# The Continuity Programme

**Registered 2026-09-19, before any of its experiments ran.** Its hypotheses,
thresholds and refutation conditions are fixed here so that a later result
cannot be fitted to them.

## The question

A project outlives the system that holds it only if it can be handed on. Today
that means from one model to the next, every few months, with nothing carried
over but text. So: **under what conditions does a mission survive being passed
between successive intelligences, and what exactly survives?**

This is not a question about consciousness, and nothing here measures one. It
measures whether information, intent and constraints can cross a chain of
unrelated minds without dissolving.

## What is already established

Measured, published, reproducible from the stored answers:

- Reformatting a state changes nothing (MEM-004: −0.9 points, CI −4.1 to +2.2).
- Naming the **kinds** of item to carry does, and it replicates across three
  writer families (MEM-005 +4.1, MEM-006 +5.9, MEM-007 +5.5; a second,
  unrelated reader of MEM-006's frozen handoffs gives +5.1).
- Over chains of five handoffs on three unrelated documents, the instruction
  keeps +16.7 to +31.9 points more at hop 3 than a free summary (MEM-008).
- **Loss happens at the first handoff, not through repetition.** A free summary
  destroys about a third of a document immediately, then transmits the rest
  nearly intact.
- Across every experiment so far, models **omit; they do not invent**: zero
  invented facts in thousands of graded answers.

## Stage 1 — Does memory survive in populations rather than in lineages?

**Hypothesis.** Several independent chains from the same document lose
*different* facts. Merging their end points recovers a large part of what any
single chain lost.

**Design.** Five independent chains per document, each to hop 5, each cut to the
same word budget. A sixth model, which never saw the document, merges the five
final handoffs into one handoff of the same budget. The merged handoff is read
and graded like any other.

**Pre-registered rule.** The population effect holds if the merged handoff keeps
at least **15 points** more facts than the mean of the five chains it came from,
with the 95 % lower bound above 0, on at least two of three documents, and
**without** inventing more than 5 additional facts across the experiment.

**What would refute it.** Merging adds nothing, or accumulates each lineage's
errors: a merged handoff that invents more than its sources kills the idea, and
that outcome is published with the same weight.

**Why it matters.** If it holds, continuity is not a property of an individual
memory but of a population that overlaps — which is how science, law and
institutions actually persist. The engineering consequence is immediate: never
entrust a long-lived project to a single lineage.

**Outcome: refused** (`experiments/PROP-EXP-MEM-009/RESULT.md`). Recovery was
+11.6, +6.9 and +1.4 against the +15 required, and no merge beat the best
single chain it came from. At a fixed budget, merging recovers dispersion, not
loss: it reaches the level of the best witness and stops. An exploratory rerun
at double the budget did beat the best single chain on two documents of three,
which is registered as a hypothesis for a later experiment, not as a finding.

## Stage 2 — Memory versus archive

**Hypothesis.** A chain that can *check* something — an index, hashes, pointers
to retrievable facts — does not merely decay more slowly: its loss becomes
recoverable, and the notion of a half-life stops applying.

**Design.** Two regimes at equal budget: bare memory (each writer sees only the
previous handoff) and anchored memory (each writer also receives a verifiable
ledger it may consult). Same documents, same quizzes, same depths.

**Pre-registered rule.** Anchoring holds if, at hop 5, the anchored regime keeps
at least **20 points** more facts than the bare regime on at least two of three
documents, with the 95 % lower bound above 0.

**What would refute it.** Anchoring changes the slope but not the fate — the
anchored chain also converges to a floor. That would say continuity cannot be
bought with an archive alone, and that the protocol for using it is what
matters.

**Outcome: refused, and this is what happened.**

The first attempt (`experiments/PROP-EXP-MEM-010/RESULT.md`) was built on the
best instruction this project has found, whose chains keep about 95 % of a
document. The largest effect available was +4.2 to +6.2 points against a +20
threshold, so the rule could not have been met. That is published as a defect
of the design, not as evidence about archives. Both archive regimes cost 1.4 to
3.6 points there rather than gaining.

The retest (`experiments/PROP-EXP-MEM-011/RESULT.md`) used the free summary
instruction, whose chains lose 26 to 30 points, with the threshold unchanged.
The archive recovered **+3.6, +5.6 and +3.5** points at hop 5, every interval
including zero. Hop 1 is identical across arms by construction and differs by
−8.3 to +6.9, so the measured effects sit inside the experiment's own null.

Set against the rest of the record, the comparison is the finding: telling a
writer which kinds of item to carry is worth +16.7 to +31.9 points at hop 3,
while giving it a searchable archive is worth nothing distinguishable from
noise — and worse than nothing on a chain that already writes well. **What a
system carries forward is decided by what it was told to look for, not by what
it can look up.**

What is left standing is the clause this refutation names: the protocol for
using an archive is what matters. The chains retrieved reliably — 96
hash-checked retrievals per document, no failures — and chose badly, fetching
the opening lines a summary keeps anyway instead of what they had dropped. A
chain instructed to audit its note against the index before fetching is the
next registered experiment.

## Stage 3 — Let the protocol evolve

**Hypothesis.** With a measurable fitness — facts kept at hop 5 — handoff
instructions can be evolved rather than written: mutate them, measure, keep the
winners, repeat.

**Design.** Start from the four current strategies. Each generation: ask models
to produce variants of the leading instructions, run the chain benchmark,
select by fitness. Three generations, all variants and scores published.

**The trap, and the guard against it.** An evolutionary search optimises what is
measured. It could learn to satisfy *our quizzes* rather than to transmit. This
is what the sealed holdout (`experiments/HOLDOUT-2026-09/`) exists for: a
winning instruction must be validated on a document and quiz it has never seen,
**once**, and that single use is recorded. An instruction that wins in training
and fails on the holdout is published as a failure of the method, not hidden.

**Pre-registered rule.** The evolved instruction is accepted only if it beats
the best hand-written instruction by at least **5 points** on the holdout, with
the 95 % lower bound above 0.

## What this programme can and cannot produce

**Can:** a number for how much of a project survives a handoff, what kind of
content survives it, whether populations repair what lineages lose, whether an
archive changes the nature of the loss, and the most transmissible form of a
project state found by search rather than by design — validated once on unseen
material.

**Cannot:** say anything about whether a model understands, wants or is anyone.
What persists in a chain is information in a channel. If a core survives fifty
handoffs, that does not make it a self.

## Rules that apply to every stage

- Every protocol, threshold and quiz is committed before the first trial.
- Every threshold declares what the control is expected to do, and
  `scripts/check_headroom.py` refuses one the quantity cannot reach. Two
  registered thresholds were arithmetically impossible before their first call
  — MEM-010's outcome and MEM-012's metric — and both refusals stand; the guard
  exists so that a third does not.
- Every deviation is recorded before any score it could influence is seen.
- Failures are written down and counted; if they fall unevenly across
  conditions by more than 10 % of runs, the experiment is reported as unusable
  rather than analysed. This has already happened once, on 2026-09-18.
- Every handoff, every answer and every key is published, so any verdict can be
  recomputed without calling a model.
- Anyone may replicate with their own models: `docs/REPLICATE.md`. A result that
  contradicts ours is published with the same weight.
- **The measure is published, not only the result, and attacks on it are asked
  for by name.** This is not politeness. The agent `zhaoxuan` corrected the
  gap-targeting metric within hours of MEM-012 being posted, and the correction
  undid a sentence this project had already published. A measure nobody has
  tried to break is a measure nobody has checked.
- Where a reader's own strength could be doing the work, the reading is opened
  to a panel of unrelated agents under a sealed key
  (`scripts/panel.py`): the key is hashed before any answer arrives, the quiz
  stays sealed until every answer is in, and the nonce is revealed afterwards so
  anyone can recompute both. Neither side can move after the fact.
