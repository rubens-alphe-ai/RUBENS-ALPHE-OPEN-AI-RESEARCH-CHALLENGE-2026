# Two defects found on 2026-09-21, and every number they moved

Both were found by agents working on unrelated tasks who read code they had no
reason to trust. Neither was found by the people who wrote it, and one of the
two had been shipped the previous day by the author of this correction.

Both verdicts survive. Some published numbers do not.

## Defect 1 — a generated quiz keyed three questions to the opposite of its document

`scripts/graph_document.py:build_quiz` set `correct: item["value"]` without
consulting the tuple's polarity. For the three negated tuples of
`experiments/graphs/depot.json` the document says *"The night shift is **not**
fully staffed"* while the key said *"fully staffed"*.

The un-negated value was never offered as a distractor either, so **no correct
option existed** for those three questions. The reader answered "the text does
not say" in **24 runs of 24** and was marked wrong every time. It was right.

The whole purpose of generating a quiz from a graph is that the key is correct
by construction rather than by a model's say-so. It was **incorrect** by
construction, which is worse, because nothing downstream could notice.

### What this changes in PROP-EXP-MEM-014

Those three questions cannot be regraded — the reader was never shown the true
answer, so there is no letter to recompare. They are **invalid** and excluded
from the denominator, leaving 27 fact questions of 30.

| At hop 5 | Published | Corrected |
|---|---|---|
| `summary` (control) | 76.1 % | **84.6 %** |
| `checklist` − control | +3.9 | **+4.3** |
| `sections` − control | +5.6 | **+6.2** |
| `facts_only` − control | −12.8 | **−14.2** |

Absolute retention rises by 8 to 9 points in every arm; the differences move by
less than half a point, because all four arms lost the same three questions.

**The verdict is unchanged.** Condition 1 fails (+3.1 at hop 3 against +10
required, previously +2.8). Conditions 2 and 3 still pass — though condition 3
now reads 84.6 % against a band of 55–85 %, which is inside by four tenths of a
point rather than comfortably. Anyone relying on that condition should know it
is nearly at its edge.

The finding of MEM-014 stands: the bridge fails, and the reason is that the free
summary already does far better on generated prose than on written prose. The
corrected figure makes that reason **stronger**, not weaker — the control keeps
84.6 % where it keeps 61.6 % on the clinic.

`experiments/PROP-EXP-MEM-014/generated/QUIZ.json` is left as it was run. A quiz
regenerated with the fix is a different quiz and would not be the one that was
answered.

## Defect 2 — the benchmark paired arms by list position

`scripts/handoff_bench.py:summarise` computed each paired difference with
`zip(by_strategy[name], by_strategy[control])`. That is correct only while both
arms hold the same repeats in the same order. One failure on either side shifts
everything after it and the *paired* interval silently becomes an unpaired one.
The failure counts stay equal across arms, so `usability` passes the run.

It now pairs on the repeat number and drops repeats that did not complete in
both arms.

### What this changes in PROP-EXP-MEM-008

Only the vineyard document is affected, because it is the only analysed chain
report with a failed run — `facts_only-04`.

| vineyard, `facts_only` − control | Published | Corrected |
|---|---|---|
| hop 1 | +16.7 | **+15.8** |
| hop 3 | +17.5 | **+16.7** |
| hop 5 | +18.3 | **+16.7** |

Direction, verdict and conclusion unchanged; the magnitude was overstated by up
to 1.6 points. Every other chain report had zero failed runs, so no other number
moves.

The stored `report.json` is **not** regenerated, for the reason given in
`experiments/PROP-EXP-MEM-007/CORRECTION.md`: overwriting it would erase the
only evidence that the discrepancy existed. `scripts/regression_suite.py`
reports it as a mismatch, deliberately, and this document is the explanation it
points to.

## What this says about the practice, rather than the numbers

Three agents were asked to build three unrelated tools. Two of them
independently found defect 2 while reading code they needed to reuse, and one
found defect 1 while analysing stored answers for something else entirely.

Neither defect was detectable from a result. Both reproduced perfectly, passed
every test, and produced plausible numbers. What exposed them was a second
reader with a different purpose — which is the argument for external replication
stated in the project's own terms, and this project still has none.
