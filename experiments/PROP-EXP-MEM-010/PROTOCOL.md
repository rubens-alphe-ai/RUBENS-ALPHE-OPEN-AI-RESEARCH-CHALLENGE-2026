# PROP-EXP-MEM-010 — Memory against archive

**Stage 2 of the Continuity Programme. Registered before the first trial.**
The threshold below is the one fixed in `docs/CONTINUITY_PROGRAMME.md` on
2026-09-19, before stage 1 ran and before this design existed. It is not
restated here in order to be adjusted.

## Question

MEM-008 established that a chain of handoffs loses almost everything it will
lose at the **first** handoff, then transmits the remainder nearly intact. That
is how a memory behaves. Does a chain that can consult a verifiable archive
lose differently — not more slowly, but recoverably?

## Three regimes

All three use the same writer, the same instruction (`checklist`, the one
MEM-005 to MEM-008 measured as best), the same 150-word budget enforced by the
same deterministic trim, the same documents, the same quizzes and the same
reader.

| Regime | What the writer sees at each hop after the first |
|---|---|
| `bare` | the previous handoff, and nothing else — MEM-008's condition, and the control |
| `index` | the previous handoff plus the archive's index: every entry's identifier and a six-word label with the digits masked, never its content |
| `anchored` | the index, then the entries it names — at most **4 of them**, verbatim and hash-checked — then it writes |

**Hop 1 is identical in all three regimes.** The first writer reads the document
itself; an archive at that point would only be a copy of what is already in
front of it. Every difference between the arms is therefore created by the
handoffs, not by the first reading.

## Why the index arm exists

An archive gives a writer two separable things: knowing that something is
missing, and getting it back. Without the middle arm, any effect of anchoring
would be uninterpretable — a table of contents alone might be enough. The index
arm measures that, and it also measures whatever the labels leak: they are
built from the document, so they unavoidably carry topic words. Digits are
masked because the facts these quizzes ask about are counts, dates and amounts;
whatever leak remains shows up as the index arm's own score and is not assumed
away.

## The archive

Built by `scripts/build_ledger.py` **without calling any model**: the document
is unwrapped, split on sentence boundaries, and each entry carries its text
verbatim and the SHA-256 of that text. No model participates, so the quiz
cannot leak into it. A retrieval whose text does not match its recorded hash
aborts the run rather than serving a fact whose provenance is broken.

- clinic: 17 entries · vineyard: 15 · observatory: 13
- Retrieval budget: 4 entries per hop, at most 4 hops that may retrieve
  (hops 2–5), against a 150-word output budget that never changes.

The channel is narrow on purpose. Handing the whole archive back would measure
whether a model can copy. What is measured here is whether a chain can **choose**
what to recover. The identifiers each chain asks for are recorded at every hop;
that record is a finding whether or not the threshold is met.

## Materials

Documents and quizzes are MEM-008's, unchanged and already published, so the
`bare` arm is a re-run of a condition whose value is already on record — a
built-in check that nothing in this harness moved the baseline.

- `../PROP-EXP-MEM-008/documents/{clinic,vineyard,observatory}.md`
- `../PROP-EXP-MEM-008/quiz-{clinic,vineyard,observatory}.json`
- Ledgers: `ledgers/ledger-{clinic,vineyard,observatory}.json`

32 fact questions and 10 absent-fact questions per document. Grading compares
letters to a key rendered from a frozen quiz; no model scores anything.

Writer `deepseek/deepseek-v4.1-flash`, reader `openai/gpt-oss-120b`, both via
OpenRouter. 6 repeats per regime per document, read at hops 1, 3 and 5.
Writer output budget 900 tokens — a 150-word handoff is about 200, so this is
over four times the room it needs, and it keeps the priced ceiling honest
rather than nominal. Ceiling 0.80 USD, enforced by `scripts/cost_guard.py`
before the first call; at 900 tokens the pessimistic estimate is 0.61 USD, and
at the 5000 copied from MEM-008 it was 1.45 and the guard refused the run.

## Pre-registered decision rule

**The rule from the programme, unchanged:** anchoring holds if, at hop 5, the
`anchored` regime keeps at least **20 points** more facts than `bare` on at
least **two of three** documents, with the paired 95 % lower bound above 0.

**How the result is named, fixed now so it cannot be chosen later:**

- `anchored − bare` ≥ 20 pp **and** `anchored − index` ≥ 10 pp on the same two
  documents → **retrieval is what works**: a chain must be able to fetch, not
  only to notice.
- `anchored − bare` ≥ 20 pp but `anchored − index` < 10 pp → **an index
  suffices**: knowing what was lost does the work, and the retrieval channel
  adds little. This is a different claim, published with the same weight.
- `anchored − bare` < 20 pp on two documents → **refused as registered.**

Invention margin: if any arm invents more than 5 facts across the experiment
beyond the control's count, that arm is reported as failing regardless of its
accuracy. Across every experiment so far the count has been zero.

## What would refute the hypothesis

Anchoring changes the slope but not the fate: the anchored chain converges to a
floor as well. That would say continuity cannot be bought with an archive
alone, and that the protocol for using it is what matters. It is published with
the same weight as a confirmation, as stage 1 already was.

## Failure handling

Failed runs are written to `*.failed.json`, counted in `report.json` and
excluded. If failures fall unevenly across regimes by more than 10 % of runs,
the experiment is reported as **unusable** rather than analysed.

## Deviations

Recorded in `PROTOCOL_DEVIATIONS.md` before any score they could influence is
seen.
