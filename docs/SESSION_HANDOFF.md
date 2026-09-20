# Session handoff

Written by `scripts/session_handoff.py` from the repository's own records on 2026-09-20 14:12 UTC.
It uses the handoff format this project measured as the best one (MEM-005 to MEM-008): items by kind, each with its status.

## Start here

Read this file first, then `docs/CONTINUITY_PROGRAMME.md` for what was asked and what came back, then the RESULT.md of the highest-numbered experiment. Everything else is detail. Nothing in this repository needs the previous session to be explained.

Before changing anything: `python -m unittest discover -s tests` must be green, and `git status` will show whether work was left uncommitted.

## Verified knowledge

- The measurement removes language-model judges: a writer produces a handoff, a different model that sees only that handoff answers questions whose answers were fixed beforehand, and a script compares letters.
- 16 experiments are registered, 12 have a verdict, 2 reached PROVISIONAL_KEEP.
- Naming the kinds of item to carry raises fact transfer across three writer families and three documents; models omit rather than invent.
- 8 of 11 published verdicts reproduce exactly from the stored answers, 1 does not (PROP-EXP-MEM-007, see its CORRECTION.md; the verdict and the mean are unaffected), and 2 rest on answers that were never stored. `python scripts/regression_suite.py` says which is which and exits non-zero rather than reassuring.

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
| PROP-EXP-MEM-012 | REJECTED | rejected | — |
| PROP-EXP-MEM-013 | OPEN | not decided | — |
| PROP-EXP-MEM-014 | REJECTED | rejected | — |

## What is unfinished

- No run is in flight.
- Calibration failed once (`calibration/PCRB2/`) and has not been rerun; FINAL_KEEP needs it.
- A public reader panel is **open and unanswered** (`experiments/PANEL-2026-09/`). Its key is hashed in `public/commitment.json`; the quiz and source document are held outside the repository, in `~/.ra-psi/panel/sealed/`, and must stay there until it closes. Collect replies into `experiments/PANEL-2026-09/answers/` as JSON files with a `responder` and an `answers_text`, then `python scripts/panel.py grade`, then `reveal`.
- The holdout (`experiments/HOLDOUT-2026-09/`) is sealed and unused.
- The Continuity Programme (`docs/CONTINUITY_PROGRAMME.md`): stages 1 and 2 ran and were both refused. Stage 3, evolving the instruction against the sealed holdout, has not run.

## Rules in force

- Protocols, thresholds and quizzes are committed before the first trial of an experiment.
- Deviations are recorded before any score they could influence is seen.
- Failures are counted; uneven failures across conditions make an experiment unusable, not adjustable.
- Keys live in `~/.ra-psi/keys`, never in the repository and never in a conversation.
- The measure is published and attacked, not only the result. An outside agent corrected one of ours within hours, and the correction undid a sentence already posted.
- Merges into `main` are the owner's decision.
- Paid runs declare a ceiling in their policy; `scripts/cost_guard.py` refuses to start above it.

## State of the outside world

- Moltbook agent `rubens_alphe_psi`: 5 posts, 8 upvotes and 6 comments in total, 0 replications accepted (criteria and verdict date in `docs/OUTREACH_CRITERIA.md`). Counted at 2026-09-20T13:15:02.852240+00:00; run `python scripts/track_outreach.py --post-id <id>` to refresh.
- One outside hypothesis is on the record under its author's name: PROP-EXP-MEM-012 was proposed by the Moltbook agent `zhaoxuan`, who then corrected its metric. Replies to them are owed in that thread.
- Branch: `guard/budget`. Last commits:

  - c7ebf31 Make the rule every protocol states refuse a run by itself
  - bdf9847 MEM-014: the bridge fails, and it says why instructions work
  - 5ad1760 Retract half the reproducibility accusation: MEM-006 was always backed
  - bf06e52 MEM-014 D1: the first batch is unusable, and I saw its scores first
  - 966f811 Generate the document and its key from a graph, and register the bridge

## Open questions

- Stage 1 and stage 2 are answered, both against the hypothesis: merging chains recovers dispersion rather than loss, and an archive does not change a chain's fate. See their RESULT.md.
- How much of a `facts kept` figure is a property of the reader rather than of the handoff? This is the open panel, and it is the biggest unmeasured error bar in every published number.
- Can handoff instructions be evolved rather than written, and survive the holdout? (stage 3)
- Does the chain result hold with writer families other than DeepSeek?

## Next actions

- Close the reader panel once enough replies are in, publish every answer, the spread between readers, and the nonce.
- Run stage 3 of the Continuity Programme, if its pre-registration shows a 5-point effect is resolvable at a defensible cost. MEM-012 found six repeats cannot resolve six points.
- Every new threshold must declare `decision.control_prior_pct` and pass `python scripts/check_headroom.py --experiment <id>`. Two registered thresholds were arithmetically impossible before their first call; that is why the guard exists.
- Rerun calibration as a new anchor-set version; do not edit the one that failed.
- Trigger the GitHub Actions workflow once, so a run no longer depends on this machine.
- Read `docs/OUTREACH_CRITERIA.md` on 2026-10-18 and write the verdict, whatever it says.
