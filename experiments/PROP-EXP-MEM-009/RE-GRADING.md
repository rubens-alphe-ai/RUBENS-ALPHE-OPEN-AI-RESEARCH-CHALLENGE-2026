# PROP-EXP-MEM-009 — a second reading of the merged notes, with the answers kept

The three recovery figures this experiment published (+11.6, +6.9, +1.4 points)
cannot be recomputed. They are not shown here to be wrong; they are shown to be
**unbacked**, and a new reading is filed beside them that is not.

## What was lost

Each `results/<document>-summary/merge-NN.json` stores the merged handoff, its
SHA-256, and a `grade` — but **not the reader's answers**, and no
`answer-key.json` was written anywhere in the experiment. The letters the reader
gave were never persisted. They cannot be recovered and **no attempt was made to
reconstruct them**: a reconstructed answer sheet would be a guess wearing the
costume of evidence.

`scripts/regression_suite.py` reports all six merge directories as
`unverifiable`, and they remain so. Nothing in `results/` was edited, added to,
or regenerated.

## What was re-read

The merged notes themselves survive, frozen and hashed. All 18 notes of the
three 150-word directories — the ones carrying the headline figures — were read
again. Each note's stored SHA-256 was verified against its stored text before it
was read; a note whose hash did not match would have been refused.

| | |
|---|---|
| Re-read | 18 merged handoffs: `clinic-summary`, `observatory-summary`, `vineyard-summary` |
| Reader | `openai/gpt-oss-120b` via OpenRouter, reading at temperature 0, low reasoning effort |
| When | 2026-09-19, 21:09–21:14 UTC |
| Script | `scripts/reread_merges.py` |
| Written to | `experiments/PROP-EXP-MEM-009/re-grading/` — **outside `results/`, deliberately** |
| Cost | 18 calls, ≈33k input tokens; estimated under $0.02 |

**This is a new reading, not a reproduction.** It uses the same reader model the
run published (`openai/gpt-oss-120b`), which makes the comparison as tight as it
can be, but a model read on a different day is a different measurement and a
difference here cannot be attributed to any one cause. The 300-word directories
were not re-read; they are exploratory and carry no registered figure.

Each record now stores the raw answers beside the grade, and each directory
carries an `answer-key.json` with the key, the rendering and the seed material.
The whole re-reading can be regraded by anyone, offline, without a model.

## What came back

| Document | Merged, published | Merged, re-read | Recovery, published | Recovery, re-read | Moved |
|---|---|---|---|---|---|
| Clinic | 73.2 % | **73.9 %** | +11.6 | **+12.3** | +0.7 |
| Observatory | 77.1 % | **75.7 %** | +6.9 | **+5.6** | −1.3 |
| Vineyard | 81.2 % | **81.9 %** | +1.4 | **+2.1** | +0.7 |

**The re-read numbers are not the published ones. Two moved up, one moved
down.** The differences are small — at most 1.4 points — and every one of them
is a whole number of quiz questions: 12 of the 18 notes scored exactly as
published, and the 6 that moved each moved by a single question (1 of 23 on the
clinic quiz, 1 of 24 on the other two). This is what re-reading the same text
with the same model looks like when nothing is wrong; it is not evidence that
the published grades were right, because nothing can be.

The source side of each figure **is** recomputable and was recomputed rather
than copied: the six MEM-008 chains behind each document were regraded from
their own stored answers and returned 61.6 %, 70.1 % and 79.9 % — the published
source means, exactly. So the recovery figures above are a pure function of
stored letters end to end, which is what the published ones are not.

## What survives the re-reading, and what does not

Survives:

- **Zero inventions, in all 18 merges, on all three documents.** The failure
  mode the rule was written to catch still did not occur.
- **No merge beat the best single chain it came from.** Re-read, the margins are
  0.0, −3.5 and −1.4 points. RESULT.md's central claim — that at a fixed budget
  merging reaches the level of the best witness and stops there — holds, and the
  clinic case is now an exact tie rather than a narrow miss.
- The ordering of the three documents, and the registered verdict: recovery is
  nowhere near the 15 points the hypothesis required. MEM-009 is still refuted
  by its own rule.

Does not survive:

- The specific values +11.6, +6.9 and +1.4 as *checkable* quantities. They stay
  published, they stay unverifiable, and the numbers a reader can check are the
  ones above, which differ from them.

## A second finding, about the key

MEM-009 rendered its quizzes with the seed `"clinic:<version>"` — the name of
the bench folder — while MEM-008 rendered the same quiz files with
`"clinic.md:<version>"`, the name of the document. The two renderings shuffle
the options differently: **17 of the 31 clinic answers fall on a different
letter.** Nothing published is wrong because of it — each side graded its own
readers against its own key, and fact accuracy does not depend on option order,
which is why the two are comparable at all. But it is a trap for exactly the
work done here: regrading MEM-008's chains against the merge run's key drops
their mean from 61.6 % to 16.7 % and would have invented a recovery of more than
forty points. `reread_merges.py` loads each side's own stored key and says why
in the code.

This is also why `merge_chains.py` now writes an `answer-key.json` recording its
seed material. Storing the answers is not enough on its own: a later reader who
has to guess which seed rendered the quiz gets a silently ruined regrade instead
of a failed one.

## The cause, fixed

`scripts/merge_chains.py` built its record with `grade=hq.grade(...)` and never
stored `answers`. It now assembles records through `merge_record`, which stores
the reader's letters beside the grade and **raises rather than build a record
without them**, and it writes an `answer-key.json` into every output folder.
Four tests in `tests/test_merge_chains.py` pin this, including one that fails if
a record is produced with no answers and one that round-trips a record through
JSON and regrades it from its own stored letters.

The published `merge-NN.json` files were not touched. The fix applies to future
runs; the six directories already on disk stay as they were published.
