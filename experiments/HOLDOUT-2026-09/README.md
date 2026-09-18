# HOLDOUT-2026-09 — sealed state and quiz

This folder is **not an experiment**. It holds a second project state, with its
own quiz, kept unused on purpose.

## Why it exists

Every experiment so far used the same project snapshot, so a design that
happened to suit that snapshot would look good for the wrong reason. The V4
contract refuses `FINAL_KEEP` without holdout evidence, and this is that
holdout: a state no design decision has been fitted to.

## What is in it

- `facts.json` — 34 facts about the project as of 2026-09-18, each with a
  status. They are real and checkable against the repository's history.
- `STATE_A.txt` and `STATE_B.json` — the same facts as prose and as named
  sections, rendered by `scripts/build_mem002_states.py --experiment
  HOLDOUT-2026-09`, which refuses to write unless every fact and status appears
  in both.
- `QUIZ.json` — 32 questions whose answer the state supports and 10 questions
  about things it never contains, in the format of `PROP-EXP-MEM-004`.
- `leak_markers.json` — tokens that exist only in the sectioned form.

## The seal

The holdout is used **once**, and only after a candidate has already passed on
the primary state (the MEM-002 / MEM-003 / MEM-004 snapshot). Using it earlier,
or tuning anything against it, destroys what it is for.

When it is used, the experiment that uses it records:

- the commit that first published this folder, as proof it predates the run;
- that no result from this state had been read before;
- the same decision rule as the passing experiment, unchanged.

Until then, nothing in this folder is read by any model, and no question here
is used to choose a design, a threshold or a model.
