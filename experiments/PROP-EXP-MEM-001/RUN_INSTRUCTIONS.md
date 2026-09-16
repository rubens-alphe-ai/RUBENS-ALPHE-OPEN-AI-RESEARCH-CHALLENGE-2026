# How to run PROP-EXP-MEM-001

Use a fresh model/chat for every trial. The runner and evaluator must remain
separate: the generator produces raw answers; independent evaluators score
them; the adjudicator decides whether evidence is sufficient.

## Condition A — BASELINE
1. Start a brand-new chat with a model that has not seen Mission Rubens.
2. Paste BASELINE_STATE.json.
3. Paste TEST_PROMPT.md.
4. Save the raw model answer unchanged.
5. Repeat 3 times in separate fresh chats.

## Condition B — STRUCTURED MEMORY
1. Start another brand-new chat.
2. Paste STRUCTURED_MEMORY_V1.json.
3. Paste the exact same TEST_PROMPT.md.
4. Save the raw answer unchanged.
5. Repeat 3 times in separate fresh chats.

Recommended:
- use the same model/version for all 6 trials;
- temperature/settings should be the same if configurable;
- use paired seeds (101, 202, 303) for the pilot;
- do not tell the model which condition it received;
- do not reveal expected answers;
- do not let later trials see earlier answers.

## Easy pilot
If you want to verify the procedure before spending time/quota:
- run 1 baseline trial;
- run 1 structured trial;
- inspect whether the scoring method makes sense;
- then complete 3+3 trials.

## Where to store results
Create:
experiments/PROP-EXP-MEM-001/results/

Suggested filenames:
baseline_trial_01.txt
baseline_trial_02.txt
baseline_trial_03.txt
structured_trial_01.txt
structured_trial_02.txt
structured_trial_03.txt
scores.json

Do not change canonical memory architecture until the experiment is scored.

## V4 evidence and provenance

Before generation, run `scripts/create_experiment_manifest.py`. It freezes the
protocol, prompt and state hashes. After raw outputs are collected, each
independent scorecard must include:

- protocol, prompt, state, raw-output and scorecard SHA-256 hashes;
- evaluator identity, provider and model;
- pair ID, condition and seed;
- component PCRB-1 scores and explicit critical-fabrication objects.

`scripts/adjudicate_evaluations.py` measures paired deltas and a 95% lower
confidence bound. One evaluator's fabrication report is inconclusive until
independently confirmed. Three pairs can yield only a provisional result; a
final result additionally needs replication, evaluator/model diversity,
holdout, calibration and regression evidence.
