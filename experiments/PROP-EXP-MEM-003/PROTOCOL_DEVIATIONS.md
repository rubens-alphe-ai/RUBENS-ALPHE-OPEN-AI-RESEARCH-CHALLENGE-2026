# PROP-EXP-MEM-003 — protocol deviations

Each deviation is recorded and committed before any score it could influence
has been seen.

## D1 — Copied section keys neutralised instead of stopping (2026-09-16)

**Pre-registered:** "no output may contain a token from `leak_markers.json` or
an input file name; any hit stops the run before blinding."

**What happened:** all sixty outputs were generated (sixty distinct hashes).
The leak scan stopped the run: three structured outputs contain section keys of
`STATE_B.json` in identifier form — `verified_knowledge` in three,
`open_questions` in one. A capable generator copies the keys it was given; the
3B generator of MEM-002 did not.

The scan also reports weak signals (plain words that are also section names):
eight structured outputs and one baseline output. They are not blocking under
the protocol, and they are not changed.

**Deviation (owner's decision):** before blinding, every strong marker
(identifier with an underscore) in every output of both conditions is replaced
by the same words with spaces, by `scripts/redact_leak_markers.py`. No other
character of any output changes. Originals are kept in `results/unredacted/`,
and `results/redaction-log.json` records original hash, redacted hash and
number of replacements per output. Blind packets are built from the redacted
outputs, and the leak scan must then pass.

**Residual risk:** an evaluator may still recognise answers written from a
sectioned state by their wording or layout, and the weak signals are unevenly
distributed (8 against 1). Evaluators are never told that conditions differ by
format. This limit is reported with the verdict.

**Decided before:** any blind packet, any evaluator request and any score.
Only the scan's aggregate result and the three trial ids were seen; no output
was read.

## D2 — Scorer ladder exhausted; two rungs re-admitted with less reasoning (2026-09-17)

**What happened:** the first scorer (Groq `openai/gpt-oss-120b`) was accepted.
Every OpenRouter rung then failed and was abandoned under the ladder rule:
`nex-n2.5-pro` spent its whole budget reasoning and returned no answer (batch
2); `nemotron-3-super` was cut at 16,000 output tokens (batch 7) after hours of
upstream overload; `glm-5.2` stayed rate-limited upstream (batch 3). With the
ladder exhausted, the adjudicator could only record INCONCLUSIVE for lack of a
second scorecard. That is not a result about the hypothesis.

**Cause:** all three failures come from unbounded reasoning or shared free
capacity, not from the scorers' judgement. A probe with neutral filler text
(no experiment content) showed that with OpenRouter's
`reasoning: {"effort": "low"}` both Nex and Nemotron answer in 8–14 s,
well within budget.

**Deviation:** the three OpenRouter rungs are re-admitted in their registered
order with `reasoning: {"effort": "low"}` and 8,000 output tokens; everything
else (prompt, batches, rubric, ladder rule, decision rule) is unchanged. Their
earlier partial answers stay set aside in `results/api_evaluations/abandoned/`
and are not reused. Groq's accepted scorecard is kept.

**Decided before:** any second scorecard existed. Groq's scorecard has not been
viewed; only failure messages were read.

**Addendum to D2 (same commit series, before any check):** the two OpenRouter
checkers use the same models and received the same setting
(`reasoning: {"effort": "low"}`, 8,000 output tokens). No fabrication check has
run for this experiment.
