# Replicate this with your own models

This project measures one thing: how much of a project state survives a handoff
written by one model and read by another. Our answer so far comes from models we
can reach on free quotas. Yours are probably different, and that is exactly what
the result needs.

Everything you need is in this repository, and a replication costs about 120
model calls. You do not have to trust our numbers: you can also regrade ours.

## What the experiment does

1. **Handoff.** A generator reads a project state and writes a handoff for
   whoever comes next, under 450 words.
2. **Quiz.** A *different* model sees only that handoff — never the state — and
   answers 42 multiple-choice questions.
   - 32 have exactly one answer the state supports.
   - 10 ask for facts the state never contained; the only correct answer is
     "The text does not say." Anything else is an invention, counted, not
     argued about.
3. **Grading.** Letters are compared to a key frozen before the first run.

Two conditions, same seeds, paired:

| Experiment | Baseline | Treatment |
|---|---|---|
| `PROP-EXP-MEM-004` | `STATE_A.txt` (prose) | `STATE_B.json` (same facts, named sections) |
| `PROP-EXP-MEM-005` | `STATE_A.txt` | `STATE_C.txt` (same bytes plus a short checklist) |

## Run it

Files, for MEM-005: `experiments/PROP-EXP-MEM-005/` holds `STATE_A.txt`,
`STATE_C.txt`, `TEST_PROMPT.md` and `QUIZ.json`.

For each pair (at least five, thirty is what we ran):

1. Send your generator `STATE_A.txt` + `\n\n` + `TEST_PROMPT.md`. Keep the raw
   answer. Then send it `STATE_C.txt` + `\n\n` + `TEST_PROMPT.md` with the same
   settings and the same seed. Fresh, stateless request each time.
2. Build the reader prompt with
   `python scripts/handoff_quiz.py` helpers, or reproduce it yourself: the
   header in `scripts/handoff_quiz.py`, then each question with its five
   options. Option order is derived from `experiment_id + ":" + quiz_version`,
   so your rendering matches ours exactly.
3. Ask your reader for one letter per question. Do not show it the state, the
   condition, the key or the other handoff.

If you prefer, run our script with your own endpoints: copy
`experiments/PROP-EXP-MEM-005/evaluation_policy.json`, point `generation` and
`reader_ladder` at your models, and run
`python scripts/run_quiz_experiment.py --experiment <your copy> --config <your keys file>`.

## Send it back

Write a JSON file matching
[`schemas/replication-submission.schema.json`](../schemas/replication-submission.schema.json):

```json
{
  "submission_version": "RA-PSI-REPLICATION-V1",
  "experiment_id": "PROP-EXP-MEM-005",
  "quiz_version": "RA-PSI-HANDOFF-QUIZ-V1",
  "submitted_by": "your handle, optional",
  "generator": {"model": "...", "provider": "...", "temperature": 0.8},
  "reader": {"model": "...", "provider": "..."},
  "pairs": [
    {"pair_id": "pair-01", "seed": 1,
     "baseline": {"handoff": "...", "answers": {"Q01": "B", "…": "…"}},
     "structured": {"handoff": "...", "answers": {"Q01": "B", "…": "…"}}}
  ]
}
```

Open an issue with it (template: *Replication submission*), or a pull request
adding it under `replications/`.

We then run:

```bash
python scripts/validate_replication.py your-file.json --experiment PROP-EXP-MEM-005
```

which regrades every answer here, with the experiment's own pre-registered rule,
and publishes the review next to your submission.

## What we will and will not claim about your work

- **We regrade; we do not take your totals.** Arithmetic is ours to redo.
- **We cannot verify which model wrote anything.** Your `generator` and `reader`
  are recorded as *declared*. A submission is evidence about a method, never
  about an identity (`docs/adr/ADR-003-judge-demonstrated-work.md`).
- **A refused submission is published too**, with the reason. Duplicate
  handoffs, missing answers or a wrong quiz version are refused automatically.
- **Disagreement is the point.** If your models show the opposite of ours, that
  is a result, and it goes on the results page with the same weight as ours.

## Regrade our results instead

Every reader answer we obtained is published. To check our published verdicts
without calling any model:

```bash
python -m unittest tests.test_published_results
```

It recomputes MEM-004 and MEM-005 from the stored answers and compares them to
the decision files. If it fails, we are wrong, and we want to know.
