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
- Every deviation is recorded before any score it could influence is seen.
- Failures are written down and counted; if they fall unevenly across
  conditions by more than 10 % of runs, the experiment is reported as unusable
  rather than analysed. This has already happened once, on 2026-09-18.
- Every handoff, every answer and every key is published, so any verdict can be
  recomputed without calling a model.
- Anyone may replicate with their own models: `docs/REPLICATE.md`. A result that
  contradicts ours is published with the same weight.
