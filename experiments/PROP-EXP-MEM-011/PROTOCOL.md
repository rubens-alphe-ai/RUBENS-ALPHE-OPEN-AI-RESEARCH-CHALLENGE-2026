# PROP-EXP-MEM-011 — Memory against archive, with room to lose

**Stage 2 of the Continuity Programme, retested. Registered before the first
trial.** This experiment exists because MEM-010 refused its rule while having
no power to meet it: its control kept 93.8 % to 95.8 % of the facts, so the
largest effect available was +4.2 to +6.2 points against a +20 threshold. That
refusal is published as `../PROP-EXP-MEM-010/RESULT.md` and stands.

## What changes, and what does not

**The threshold does not change.** +20 points at hop 5 on at least two of three
documents, with the paired 95 % lower bound above 0, as fixed in
`docs/CONTINUITY_PROGRAMME.md` on 2026-09-19. It is reachable here; it was not
there.

**The instruction changes, for every arm equally.** MEM-010 gave all three arms
the `checklist` instruction — the best one this project has found, which by
itself carries about 95 % of a document through five handoffs. Here all three
arms use the free `summary` instruction, whose hop-5 scores on these same three
documents are 61.6 %, 79.9 % and 70.1 % (MEM-008). Headroom is 20 to 38 points.

Everything else is identical: same three regimes, same archive, same retrieval
budget of four entries per hop, same 150-word limit enforced by the same
deterministic trim, same documents, same quizzes, same writer, same reader, six
repeats, read at hops 1, 3 and 5.

## Why this is the right comparison and not a rescue

The question the programme asked is whether an archive changes the *nature* of
a chain's loss. A chain that is not losing cannot answer it. Choosing an arm
that loses is not lowering a bar; the bar is where it was, and the measurement
now has the range to reach it.

The cost of this choice is stated in advance: `summary` is a worse instruction,
so a positive result here would establish that an archive repairs a **weak**
handoff, not that it improves a good one. MEM-010 already indicates it does not
improve a good one — it cost 1.4 to 3.6 points there. If both hold, the
conclusion is that an archive substitutes for a good instruction rather than
adding to one, which is a more useful claim than either result alone.

## The three regimes

| Regime | What the writer sees at each hop after the first |
|---|---|
| `bare` | the previous handoff, and nothing else — the control |
| `index` | the previous handoff plus the archive's index: identifiers and six-word labels with digits masked, never content |
| `anchored` | the index, then at most **4** entries it names, verbatim and hash-checked, then it writes |

Hop 1 is identical under all three regimes: the first writer reads the document
itself, so every difference between the arms is created by the handoffs.

## Materials

- Documents and quizzes: MEM-008's, unchanged and already published.
- Archive: MEM-010's ledgers, unchanged — built without calling any model, so
  the quiz cannot leak into them. A retrieval that fails its hash aborts the run.
- Writer `deepseek/deepseek-v4.1-flash` (output budget 900 tokens), reader
  `openai/gpt-oss-120b`, both via OpenRouter.
- Ceiling 0.80 USD, enforced by `scripts/cost_guard.py` before the first call.

## Pre-registered decision rule

- `anchored − bare` ≥ 20 pp with the paired 95 % lower bound above 0, on at
  least two of three documents → the hypothesis holds, and then:
  - also `anchored − index` ≥ 10 pp on those documents → **retrieval is what
    works**;
  - otherwise → **an index suffices**: knowing what was lost does the work.
- Otherwise → **refused as registered.**

An arm that invents more than 5 facts beyond the control across the experiment
is reported as failing regardless of its accuracy.

## What would refute the hypothesis

An anchored chain that converges to the same floor as a bare one. That would
say continuity cannot be bought with an archive alone, and that the protocol
for using it is what matters. It is published with the same weight as a
confirmation, as stage 1 and MEM-010 already were.

## Failure handling

Failed runs are written to `*.failed.json`, counted and excluded. If failures
fall unevenly across regimes by more than 10 % of runs, the experiment is
reported as **unusable** rather than analysed.

## Deviations

Recorded in `PROTOCOL_DEVIATIONS.md` before any score they could influence is
seen.
