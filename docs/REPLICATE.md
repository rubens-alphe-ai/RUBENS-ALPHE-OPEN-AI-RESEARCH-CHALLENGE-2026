# Replicate this with your own models

This project measures one thing: how much of a project state survives a handoff
written by one model and read by another. Our answer so far comes from models we
can reach on free quotas. Yours are probably different, and that is exactly what
the result needs.

You do not have to trust our numbers: you can also regrade ours.

## One command

You need an OpenAI-compatible `/chat/completions` endpoint, two model ids and a
file containing your API key. Nothing else: no dependencies outside the Python
standard library, no configuration file to write, no JSON to write by hand.

```bash
git clone https://github.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026.git
cd RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026

python scripts/replicate.py \
    --endpoint https://api.groq.com/openai/v1/chat/completions \
    --writer-model llama-3.3-70b-versatile \
    --reader-model openai/gpt-oss-120b \
    --api-key-file ~/keys/provider.key
```

That runs five pairs — twenty model calls — and ends like this:

```
pair-01: fact accuracy 68.8% -> 75.0%, inventions 1 -> 0
...
pairs completed: 5
paired delta (treatment minus baseline): +6.2 pp, 95% CI [+1.4, +11.0]
inventions: 3 in baseline, 1 in structured
this run's own verdict under the experiment's frozen rule: PROVISIONAL_KEEP

submission written to: replications/replication-PROP-EXP-MEM-005-20260919T134500Z.json
Send it back by opening an issue with the 'Replication submission' template at
https://github.com/rubens-alphe-ai/RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026/issues
(or a pull request adding the file under replications/).
```

Those numbers are the shape of the output, not a result. Yours are the point.

Attach that file to the issue and you are done: it already satisfies
[`schemas/replication-submission.schema.json`](../schemas/replication-submission.schema.json),
so nothing is left for you to write by hand.

### Worth knowing before you spend anything

- `--pairs 5` is the default and the fewest a submission may carry. **We ran
  30**; that is 120 calls, and it is what makes an interval worth reading.
- Each pair is four calls: two handoffs written, two quizzes answered.
- `--dry-run` checks the experiment files, your key file and your arguments,
  and calls nothing.
- Use a **different** model for `--writer-model` and `--reader-model`. The
  script warns you when they match, because a reader that shares the writer's
  weights is measuring something else.
- The default experiment is `PROP-EXP-MEM-005`. `--experiment PROP-EXP-MEM-004`
  runs the other one.
- The key file is passed by path and opened by the HTTP adapter at call time.
  The script never reads it, never prints it, and never writes it into the
  submission.
- Failed calls are counted per condition and printed with the result. Only
  transient errors (429, 5xx, timeouts) are retried, the same number of times
  in both conditions, and every attempt is still counted. If the losses land
  mostly on one condition, the script says so loudly: a paired series that
  loses more trials in one arm than in the other is not evidence here.
- If fewer than five pairs survive, the script writes what it did get to a file
  named `...incomplete.json`, says it is not a submission, and exits non-zero.
- Other flags: `--temperature`, `--writer-max-tokens`, `--reader-max-tokens`,
  `--extra-body '{"reasoning_effort": "low"}'` for provider-specific fields,
  `--provider`, `--submitted-by`, `--notes`, `--out`. `--help` lists them all.

Everything below explains what that command does, and how to do it by hand
instead.

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

## Run it by hand

You do not have to use the script. Everything it does is written out here.

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

`scripts/replicate.py` has already written this file for you; if you used it,
skip to the last paragraph of this section. Otherwise, write a JSON file
matching
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
