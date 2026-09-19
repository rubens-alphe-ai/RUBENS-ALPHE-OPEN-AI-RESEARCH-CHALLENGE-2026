# Session handoff

Written by `scripts/session_handoff.py` from the repository's own records on 2026-09-19 16:35 UTC.
It uses the handoff format this project measured as the best one (MEM-005 to MEM-008): items by kind, each with its status.

## Verified knowledge

- The measurement removes language-model judges: a writer produces a handoff, a different model that sees only that handoff answers questions whose answers were fixed beforehand, and a script compares letters.
- 13 experiments are registered, 10 have a verdict, 2 reached PROVISIONAL_KEEP.
- Naming the kinds of item to carry raises fact transfer across three writer families and three documents; models omit rather than invent.
- Every published verdict can be recomputed from the stored answers: `python -m unittest tests.test_published_results`.

## Experiments and their status

| Experiment | Status | Verdict | Effect |
|---|---|---|---|
| PROP-EXP-MEM-001 | REJECTED | REJECT | — |
| EXP-EVAL-001 | PROPOSED | not decided | — |
| EXP-REG-001 | PROPOSED | not decided | — |
| PROP-EXP-MEM-002 | REJECTED | REJECT | — |
| PROP-EXP-MEM-003 | OPEN | not decided | — |
| PROP-EXP-MEM-004 | REJECTED | REJECT | -0.9 pp (-4.1 to 2.2) |
| PROP-EXP-MEM-005 | INCONCLUSIVE | INCONCLUSIVE | +4.1 pp (1.5 to 6.6) |
| PROP-EXP-MEM-006 | PROVISIONAL_KEEP | PROVISIONAL_KEEP | +5.9 pp (3.5 to 8.2) |
| PROP-EXP-MEM-007 | PROVISIONAL_KEEP | PROVISIONAL_KEEP | +5.5 pp (3.7 to 7.2) |
| PROP-EXP-MEM-008 | PROVISIONAL_KEEP | provisional keep | — |
| PROP-EXP-MEM-009 | REJECTED | rejected | — |
| PROP-EXP-MEM-010 | REJECTED | rejected | — |
| PROP-EXP-MEM-011 | REJECTED | rejected | — |

## What is unfinished

- No run is in flight.
- Calibration failed once (`calibration/PCRB2/`) and has not been rerun; FINAL_KEEP needs it.
- The holdout (`experiments/HOLDOUT-2026-09/`) is sealed and unused.
- The Continuity Programme (`docs/CONTINUITY_PROGRAMME.md`): stages 1 and 2 ran and were both refused. Stage 3, evolving the instruction against the sealed holdout, has not run.

## Rules in force

- Protocols, thresholds and quizzes are committed before the first trial of an experiment.
- Deviations are recorded before any score they could influence is seen.
- Failures are counted; uneven failures across conditions make an experiment unusable, not adjustable.
- Keys live in `~/.ra-psi/keys`, never in the repository and never in a conversation.
- Paid runs declare a ceiling in their policy; `scripts/cost_guard.py` refuses to start above it.

## State of the outside world

- Moltbook agent `rubens_alphe_psi`: 2 upvotes, 0 comments, 0 replications accepted (criteria and verdict date in `docs/OUTREACH_CRITERIA.md`).
- Branch: `guard/budget`. Last commits:

  - 916bd8f Stop publishing a decided experiment as not decided
  - 0220b3e MEM-010: refused as registered, and it could not have passed
  - adc2d7b Publish the chain results, and the refutation, where agents read
  - e629f67 Price the chain design in the budget guard, and cap the writer accordingly
  - 8928a0b Pre-register PROP-EXP-MEM-010: memory against archive

## Open questions

- Does merging several independent chains recover what each lost? (Continuity Programme, stage 1)
- Does a checkable archive change the nature of the loss, or only its slope? (stage 2)
- Can handoff instructions be evolved rather than written, and survive the holdout? (stage 3)
- Does the chain result hold with writer families other than DeepSeek?

## Next actions

- Run stage 3 of the Continuity Programme, or first test whether a chain told how to use an archive chooses differently from one merely given it.
- Rerun calibration as a new anchor-set version; do not edit the one that failed.
- Trigger the GitHub Actions workflow once, so a run no longer depends on this machine.
- Read `docs/OUTREACH_CRITERIA.md` on 2026-10-18 and write the verdict, whatever it says.
