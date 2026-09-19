# PROP-EXP-MEM-010 — Result: refused as registered, and the test could not have passed

**Stage 2 of the Continuity Programme fails its rule, and the rule could not
have been met.** The registered threshold was +20 points at hop 5 on two
documents of three. The control kept 93.8 % to 95.8 % of the facts, so the
largest effect arithmetically available was **+4.2 to +6.2 points**. The
experiment was refused before it began, by its own design, and I did not see it
until the numbers came back.

That is the finding worth publishing here. The second one is that anchoring, at
this budget, gives nothing at all.

## What was measured

54 chains of five handoffs — three regimes × three documents × six repeats —
with **no failed run anywhere**. Every arm used the same writer, the same
instruction, the same 150-word budget, the same quizzes and the same reader.

| Document | bare (control) | index − bare | anchored − bare | 95 % CI | Headroom |
|---|---|---|---|---|---|
| Clinic | 94.2 % | +2.2 | −3.6 | −16.3 to +9.1 | 5.8 |
| Vineyard | 95.8 % | +0.7 | −1.4 | −3.6 to +0.9 | 4.2 |
| Observatory | 93.8 % | −1.4 | −1.4 | −7.4 to +4.6 | 6.2 |

Headroom is 100 % minus the control: the most any archive could possibly have
added. **Zero inventions in all three regimes, on all three documents**, across
432 absent-fact answers — the count has now been zero in every experiment this
project has run.

## The defect, named plainly

I built the archive arms on top of the **best** instruction this project has
found. The checklist already carries about 95 % of a document through five
handoffs; MEM-008 measured it at 91.3 %, 96.5 % and 92.4 %, and this run
reproduces it at 94.2 %, 95.8 % and 93.8 % in a different harness written
months apart. The reproduction is worth something on its own. But a control
that loses almost nothing leaves nothing for an archive to recover.

The threshold of +20 points was fixed on 2026-09-19, before this design
existed, against a picture of chains decaying steadily. MEM-008 had already
shown they do not: **loss happens at the first handoff, and the checklist
prevents most of it.** I registered a threshold from the earlier picture and
then built the experiment on the arm that had refuted it.

The rule is applied as written: **refused**. But the refusal carries no evidence
against anchoring. It is evidence about the design.

## What the run does say

Both archive regimes cost a little rather than gaining. The anchored arm is
1.4 to 3.6 points below the control on all three documents, and it writes
longer handoffs (median 130–149 words against 118–128), close enough to the
limit that two vineyard runs and one observatory run were cut. The most
plausible reading — not established here — is that retrieved verbatim sentences
compete for a fixed budget with what the note already carried. **An archive is
not free: reading from it costs the space it gives back.**

The chains also agree on what to look up. Across 96 retrievals per document
they touched only 12 to 14 distinct entries of 13 to 17, and the ranking is
stable: the opening description of the organisation, its headline quantities,
and the open question at the end. Independently-run chains converge on the same
handful of anchors without coordinating.

## What happens next, registered before it runs

The question is untested, not answered. It is retested in **PROP-EXP-MEM-011**
against an arm with room to lose: the free `summary` instruction, which keeps
61.6 %, 79.9 % and 70.1 % at hop 5 on these same three documents. There the
headroom is 20 to 38 points and a +20 point effect is reachable. The design,
the threshold and the naming rule are fixed in that experiment's protocol
before the first call, and this document is the reason it exists.

## Limits

- One writer family, one reader, three short documents in prose.
- The retrieval channel is four entries per hop; a wider one was not tried.
- The index labels are built from the document and carry topic words with their
  digits masked. The index arm exists to measure that leak; it measured ±2.2
  points, which at this ceiling is not informative either.
- The holdout stays sealed.
