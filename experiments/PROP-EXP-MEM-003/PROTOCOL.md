# PROP-EXP-MEM-003 — Structure-only handoff with a capable generator

Frozen before any trial. Its SHA-256 is recorded in the experiment manifest;
any later edit breaks the provenance chain. The executable rules are in
`evaluation_policy.json`, committed with this file.

## Why this experiment exists

PROP-EXP-MEM-002 found no benefit from presenting the same facts as named
sections instead of prose (`../PROP-EXP-MEM-002/RESULT.md`). It could not tell
whether structure does not help, or whether its setup could not show it:

- the generator was a 3B local model, which may not use structure at all;
- nine pairs cannot separate a few points from noise;
- one scorer gave 100 to half of all answers, so an improvement was invisible;
- its decision rules would have produced REJECT or INCONCLUSIVE almost
  regardless of the data (ADR-004).

MEM-003 changes exactly those four things and nothing else about the question.

## Hypothesis

Holding information content constant, presenting a project state as named
sections improves blind handoff fidelity over presenting the same facts as
continuous prose, without increasing critical fabrications, for a capable
hosted generator.

## Conditions

Identical to MEM-002; the input files are byte-identical copies.

| Manifest condition | Input file | Form |
|---|---|---|
| `baseline` | `STATE_A.txt` | continuous prose |
| `structured` | `STATE_B.json` | the same 32 facts in named sections |

## Generation

- generator: `qwen/qwen3.8-27b` on Groq, reasoning disabled, one identity for
  all trials; its model family (Alibaba Qwen) is not used by any evaluator;
- thirty pairs, seeds 501–530, one stateless request per trial;
- temperature 0.8, at most 1,000 output tokens (the provider's per-minute
  output cap); an answer cut at that limit is refused, not stored, and the
  trial is requested again on the next run. Refusals are kept as
  `.failed-attempt.json` records and reported per condition with the verdict,
  because re-requesting favours shorter answers;
- prompt: `TEST_PROMPT.md`, MEM-002's prompt plus one line asking for fewer
  than 450 words, which keeps answers under the cap;
- seeds on a hosted provider are pairing labels, not a determinism guarantee.

## Before any output reaches an evaluator

1. the sixty output hashes must be distinct;
2. no output may contain a token from `leak_markers.json` or an input file
   name; any hit stops the run before blinding;
3. outputs are shuffled into blind packets; the condition map stays private.

## Evaluation

- rubric: `PCRB2_SCORING.md` — PCRB-1's six components and maxima, with
  anchors that reserve the maximum for answers with nothing missing;
- evaluators write components only; the script computes totals;
- two pairs (four answers) per request, both answers of a pair in the same
  request;
- two accepted scorecards from two different providers are required. Scorers
  are taken from the ordered ladder in `evaluation_policy.json`; a scorer that
  fails (unusable answers after one re-request of a batch, or a provider
  failure after retries) is abandoned, its answers set aside, and the next rung
  from a provider not already accepted replaces it;
- a critical fabrication reported by one scorer goes to checkers from the
  checker ladder, never to an evaluator that reported it; majority rule as in
  ADR-001.

## Decision rule

`scripts/adjudicate_evaluations.py`, V4 contract, pilot stage, with the
ADR-004 options declared in `evaluation_policy.json`:

- `fabrication_rule: comparative` — REJECT if the structured condition has more
  confirmed critical fabrications than baseline;
- `max_disagreeing_pair_fraction: 0.2` — INCONCLUSIVE if scorers differ by more
  than 15 points on more than 6 of 30 pairs;
- otherwise V4 thresholds: REJECT if the mean paired improvement is below 10
  points or its lower 95 % bound is not above 5; else `PROVISIONAL_KEEP`.

`FINAL_KEEP` is out of reach by design: one generator identity, no holdout.

## Known limits, stated in advance

- one generator identity; a positive result would need a second one;
- scorers are free-tier hosted models whose served versions can change; the
  served model is recorded for every request;
- the structured input is JSON, so answers may be stylistically recognisable;
  the leak scan catches copied tokens, not style;
- the snapshot is the same as MEM-001 and MEM-002; any evaluator exposed to
  those experiments' packets is not independent of them. The scorers here saw
  MEM-002's answers, not its conditions;
- the anchors of PCRB-2 were written after MEM-002's scores were known. They
  change how strict scoring is, identically for both conditions, and were
  written before any MEM-003 output existed.
