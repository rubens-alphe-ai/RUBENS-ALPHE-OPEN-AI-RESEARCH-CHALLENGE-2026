# Session handoff

Written by `scripts/session_handoff.py` from the repository's own records on 2026-09-19 08:44 UTC.
It uses the handoff format this project measured as the best one (MEM-005 to MEM-008): items by kind, each with its status.

## Verified knowledge

- The measurement removes language-model judges: a writer produces a handoff, a different model that sees only that handoff answers questions whose answers were fixed beforehand, and a script compares letters.
- 10 experiments are registered, 7 have a verdict, 2 reached PROVISIONAL_KEEP.
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

## What is unfinished

- No run is in flight.
- Calibration failed once (`calibration/PCRB2/`) and has not been rerun; FINAL_KEEP needs it.
- The holdout (`experiments/HOLDOUT-2026-09/`) is sealed and unused.
- The Continuity Programme (`docs/CONTINUITY_PROGRAMME.md`) is registered; stage 1 has not run.

## Rules in force

- Protocols, thresholds and quizzes are committed before the first trial of an experiment.
- Deviations are recorded before any score they could influence is seen.
- Failures are counted; uneven failures across conditions make an experiment unusable, not adjustable.
- Keys live in `~/.ra-psi/keys`, never in the repository and never in a conversation.
- Paid runs declare a ceiling in their policy; `scripts/cost_guard.py` refuses to start above it.

## State of the outside world

- Moltbook agent `rubens_alphe_psi`: 2 upvotes, 0 comments, 0 replications accepted (criteria and verdict date in `docs/OUTREACH_CRITERIA.md`).
- Branch: `guard/budget`. Last commits:

  - b0e6539 MEM-008: the instruction wins on all three documents, and loss happens at the first handoff
  - 6ecd48e Pre-register PROP-EXP-MEM-008: how fast a handoff decays over five hops
  - d92251f MEM-006 and MEM-007: PROVISIONAL_KEEP, the checklist replicates across three writer families
  - 8b867ea MEM-006: ceiling at the 0.50 USD the owner approved per experiment
  - 34b326e MEM-006: give the reader room to finish one long handoff

## Open questions

- Does merging several independent chains recover what each lost? (Continuity Programme, stage 1)
- Does a checkable archive change the nature of the loss, or only its slope? (stage 2)
- Can handoff instructions be evolved rather than written, and survive the holdout? (stage 3)
- Does the chain result hold with writer families other than DeepSeek?

## Next actions

- Run stage 1 of the Continuity Programme.
- Rerun calibration as a new anchor-set version; do not edit the one that failed.
- Trigger the GitHub Actions workflow once, so a run no longer depends on this machine.
- Read `docs/OUTREACH_CRITERIA.md` on 2026-10-18 and write the verdict, whatever it says.
