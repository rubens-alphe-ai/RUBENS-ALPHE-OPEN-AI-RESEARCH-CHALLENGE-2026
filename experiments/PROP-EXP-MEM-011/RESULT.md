# PROP-EXP-MEM-011 — Result: an archive does not change the fate of a chain

**Stage 2 of the Continuity Programme is refused as registered.** Given a
verifiable archive and a channel to fetch from it, a decaying chain of handoffs
recovers **+3.6, +5.6 and +3.5 points** at hop 5 against the +20 required. No
confidence interval excludes zero on any document.

This time the test had the range to succeed: the control lost 26 to 30 points,
so an effect of +20 was available on all three documents. It did not appear.

## What was measured

54 chains of five handoffs — three regimes × three documents × six repeats —
**no failed run anywhere**, as in MEM-010. Same writer, same free `summary`
instruction in every arm, same 150-word budget, same quizzes, same reader.

| Document | bare (control) | headroom | index − bare | anchored − bare | 95 % CI |
|---|---|---|---|---|---|
| Clinic | 73.9 % | 26.1 | −2.9 | **+3.6** | −8.8 to +16.0 |
| Vineyard | 73.6 % | 26.4 | +5.6 | **+5.6** | −2.6 to +13.7 |
| Observatory | 70.1 % | 29.9 | −2.1 | **+3.5** | −9.6 to +16.6 |

Zero inventions in all three regimes on all three documents, across 432
absent-fact answers. The count is still zero in every experiment this project
has run.

## The experiment carries its own null, and the effect sits inside it

**Hop 1 is identical in all three regimes by construction**: the first writer
reads the document itself and no archive exists for it to consult. Any
difference measured at hop 1 is therefore pure sampling noise from a stochastic
writer, and it is measurable:

| Document | index − bare at hop 1 | anchored − bare at hop 1 |
|---|---|---|
| Clinic | −3.6 | −2.2 |
| Vineyard | +5.6 | +6.9 |
| Observatory | −6.2 | −8.3 |

Arms that are the same thing differ by −8.3 to +6.9 points at six repeats. The
anchored effects at hop 5 — +3.5 to +5.6 — fall **inside** that band. Nothing
here distinguishes an archive from a coin.

This is a better answer than the confidence intervals alone, and it cost
nothing: the null was built into the design rather than argued about
afterwards.

## What this says, against what the programme expected

The registered refutation condition was written out in advance:

> Anchoring changes the slope but not the fate — the anchored chain also
> converges to a floor. That would say continuity cannot be bought with an
> archive alone, and that the protocol for using it is what matters.

That is what happened. The anchored chains land on the same floor as the bare
ones, two to six points above it, inside the noise.

**Put next to what this project has already measured, the comparison is the
result:**

| Intervention | Effect |
|---|---|
| Telling the writer which kinds of item to carry | **+16.7 to +31.9 pp** at hop 3 (MEM-008), replicated across three writer families (MEM-005/006/007) |
| Giving the writer a verifiable archive and four retrievals per hop | **+3.5 to +5.6 pp** at hop 5, inside the noise floor (this experiment) |
| Giving a strong chain the same archive | **−1.4 to −3.6 pp** (MEM-010) |

An archive is roughly five times less valuable than an instruction, and on a
chain that is already writing well it is worse than nothing. **What a system
carries forward is decided by what it was told to look for, not by what it can
look up.**

## Why an archive helps so little, as far as this can tell

Three observations, none of them established:

- **Retrieval competes with the note.** Anchored handoffs run 8 to 23 words
  longer at the same limit; the fetched sentences take space that the existing
  content was using. MEM-010 saw the same cost with no benefit.
- **The chains look up what they already have.** Across 96 retrievals per
  document they touched 9 to 12 distinct entries out of 13 to 17, and the
  ranking is dominated by the document's opening lines — the part a summary
  keeps anyway. No chain went looking for what it had dropped.
- **Noticing is not recovering.** The index-only arm is flat to negative
  (−2.9, +5.6, −2.1). Being shown that entry 14 exists does not make a writer
  reconstruct it, and it costs attention.

The second point is the one worth attacking next: the retrieval channel worked
mechanically — 96 hash-checked retrievals per document, no failures — but the
chains chose badly. That is a protocol problem, not an archive problem, and it
is exactly what the programme's refutation clause predicted would be left.

## Limits

- One writer family, one reader, three short prose documents.
- Four retrievals per hop; a wider channel was not tried, and MEM-010 suggests
  a wider one would cost more budget rather than less.
- The writer was never told *how* to use the archive beyond being given it. A
  chain instructed to audit its note against the index before fetching might
  choose differently; that is the next registered experiment, not a claim here.
- Six repeats per arm. The hop-1 null shows that is enough to see a 20-point
  effect and not enough to resolve a 5-point one.
- The holdout stays sealed.
