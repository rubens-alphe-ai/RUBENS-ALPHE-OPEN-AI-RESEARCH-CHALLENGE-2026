# PROP-EXP-MEM-014 — Result: the bridge fails, and it says why instructions work


> **Corrected 2026-09-21.** Some numbers below moved after a defect was found in the code that produced them. The verdict is unchanged. See [`docs/CORRECTIONS-2026-09-21.md`](../../docs/CORRECTIONS-2026-09-21.md) for every number that moved and why the stored files were not overwritten.

**The generator is not usable for this project's main question.** Two of the
three registered conditions passed. The one that failed is the one that matters.

24 chains, **no failed run**, zero inventions in all four arms.

| # | Registered condition | Measured | |
|---|---|---|---|
| 1 | `checklist − summary` at hop 3 ≥ **10 pp**, lower bound above 0 | **+2.8** (−9.4 to +15.0) | **FAIL** |
| 2 | Loss from hop 1 to hop 5 ≤ half the loss taken at hop 1 | 3.3 against 10.3 allowed | PASS |
| 3 | `summary` at hop 5 between 55 % and 85 % | 76.1 % | PASS |

By the naming rule fixed before the run: **condition 1 failing means the
instruction effect does not reproduce on generated prose, and the programme
stops using generated documents for that question.** That is applied, not
argued with.

## The shape and the level reproduce. The effect does not.

| | hop 1 | hop 3 | hop 5 |
|---|---|---|---|
| Generated document, `summary` | 79.4 % | 77.8 % | 76.1 % |
| Clinic, written, `summary` (MEM-008) | 65.2 % | 62.3 % | 61.6 % |

The cliff-then-plateau shape is there: a fifth is lost at the first handoff and
almost nothing after. The retention sits inside the band observed on written
documents. On those two counts the renderer produces something that behaves
like prose.

But on the written documents the checklist instruction was worth **+16.7 to
+31.9 points**. Here it is worth **+2.8**, and the interval spans zero.

## Why, and this is the useful part

Look at what the free summary achieves: **79.4 % at the first handoff, against
65.2 % on the clinic.** The control is not failing. It is doing far better than
it does on written prose, and that is what leaves the instruction nothing to
add.

The generated document is one atomic fact per sentence, with no narrative, no
repetition and no context binding facts together. A free summary of a fact list
is a shorter fact list. The checklist instruction asks a writer to carry items
by kind with their status — **and the document is already in that form.**

So the most plausible reading, which this experiment supports but does not
establish:

> The instruction effect exists because written prose **buries** facts in
> narrative. It is worth +16.7 to +31.9 points on prose that hides things. On
> prose with nothing to hide, it is worth nothing measurable.

That reframes what MEM-005 to MEM-008 measured. The checklist is not making a
model remember better. It is making a model **excavate** — and its value is a
function of how deeply the source buries what it carries.

`facts_only` supports the same reading from the other side: on written documents
it ranged from −4.3 to +18.3 against the summary; here it is **−16.1**, with the
interval excluding zero on every hop. Turning an already-atomised document into
a list of facts destroys the little structure it had.

## What this does not refute

- The written-document results stand. Nothing here touches MEM-005 to MEM-008.
- The renderer is not shown to be broken. Conditions 2 and 3 passed, and zero
  inventions in 24 chains says the generated quiz does not bait a reader.
- Generated documents are refused **for measuring instruction effects**. They
  are not refused for questions where the document's form is not the variable —
  raw retention, decay shape, dispersion. Whether they are sound for those is
  untested, and this result is not permission.

## What would make the generator work for the main question

Not a fix to the renderer. A different graph: one whose prose has redundancy,
narrative order, and facts distributed across sentences rather than one to one.
That is a larger design than a template change, and registering it would mean
first establishing what "buries a fact" means as a measurable property of a
document — which the project cannot currently state.

The `spread` parameter already in `scripts/graph_document.py` moves in that
direction and was not varied here; it was held at the default so that a single
condition changed against MEM-008. Varying it is the obvious next test, and it
is not this one.

## Process

The first batch of this experiment was **unusable** — 6 failed runs of 24,
falling 2/2/2/0 across the arms, caused by a reader token budget I halved by
launching the benchmark from a command line that could not set it. The scores
were seen before the cause was found, which departs from this project's own
rule. All of that is in `PROTOCOL_DEVIATIONS.md`, and the batch is kept at
`results/superseded_reader2000/` rather than deleted. The rerun reported here
had zero failures.

## Limits

- One generated document, one graph, one writer, one reader, six repeats.
- `spread` held at its default, so dispersion was not varied.
- The explanation offered above is a reading of two numbers, not a measurement.
  It predicts that the instruction effect should scale with how much a document
  buries; nothing here tests that.
- The holdout stays sealed.
