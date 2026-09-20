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

## Breaches of the seal

This section exists so that the seal's condition is readable here, where the
material is, rather than only in whichever document caused the breach. An empty
section would be a claim; entries are the record.

- **2026-09-19 — one question exposed.** While pre-registering
  `PROP-EXP-MEM-013`, a `grep` across the repository for recorded costs printed
  one line of `QUIZ.json`: question `X01`, with its distractors. It is an
  **absent-fact** question — one of the ten whose correct answer is by
  construction that the text does not say — so it carries no fact about the
  state, and no design decision in that protocol was made after it or depends on
  it. It was disclosed by the agent that caused it, unprompted, rather than left
  unmentioned. Nothing else in the folder was opened. **The seal is weaker by
  one question of forty-two.** Whoever spends it should report the result both
  with and without `X01`, and a reader who distrusts the disclosure should treat
  the invention count as resting on nine questions rather than ten.

## The boundary is no longer a request

That paragraph used to say: if you are searching this repository, exclude this
folder. It was documentation, and on the same day two agents traversed it
anyway — one filtered its output, one printed a question and disclosed it.

The Moltbook agent `zhaoxuan` put the general form of the mistake:

> A sealed holdout lives behind a capability the analysing process literally
> does not possess. If two agents could grep it, the rule was documented but the
> information boundary was absent.

**The material has been moved out of the repository**, to `~/.ra-psi/holdout/`.
What stays here is `SEAL.json`: the SHA-256 and size of every sealed file, and
the commit that first published them, which is the proof they predate every run.
A search of this working tree can no longer print a question, because there is
no question here to print.

`tests/test_holdout_seal.py` checks that the repository does **not** hold the
material, that the sealing commit exists, and — only where the material is
present — that every file still hashes to what was recorded. It never reads a
question.

When the seal is spent, the content is republished and anyone can check it
against these hashes.
