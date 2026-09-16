# PROP-EXP-MEM-002 — protocol deviations

Each deviation is recorded and committed before any score it could influence
has been seen.

## D1 — Scoring in three batches instead of one prompt (2026-09-16)

**Pre-registered:** one evaluator prompt containing all eighteen shuffled
answers (`PROTOCOL.md`, Evaluation).

**What happened:** the operator relay was replaced by API evaluators on free
tiers. Measured limits, read from the providers' own response headers:

- Groq, every chat model eligible for blind scoring: 8,000 tokens per minute.
  The single prompt is about 10,800 tokens and was refused (HTTP 413).
  `groq/compound` allows 70,000 but is a tool-using system that can search the
  web, where this repository is public; it was rejected to preserve blinding.
- Mistral: the workspace reported 0 requests per minute (HTTP 429) until the
  owner activates the free plan.

**Deviation:** each evaluator scores three requests of six answers.

**Controls:**

- both answers of every pair are in the same batch, so any difference in an
  evaluator's severity between batches affects both conditions of a pair
  equally and cancels in the paired delta;
- each batch therefore holds three answers of each condition;
- the rubric and instructions are identical in every batch;
- pair grouping and answer order are drawn from a seed derived from the frozen
  protocol hash, so they are reproducible;
- every batch prompt is scanned: no condition label, no state file name;
- both evaluators receive exactly the same three batches.

**Residual risk:** an evaluator sees six answers instead of eighteen, so its
sense of the full range is narrower, and absolute scores may compress. Paired
deltas, which the decision rule uses, are protected by the pairing; absolute
means are less comparable with MEM-001, which was scored in one prompt.

**Decided before:** any scorecard for this experiment existed.

## D2 — Second scorer: OpenRouter / Gemma instead of Mistral (2026-09-16)

**Pre-registered:** two independent evaluators from different providers; no
specific provider was named. Mistral had been planned operationally.

**What happened:** Mistral's API kept answering HTTP 429 with a per-minute
request limit of 0, although the account is on the free plan and its
organisation limits page shows 20,000 tokens per minute. The cause was not
found in the console.

**Deviation:** the second scorer is `google/gemma-4-31b-it:free` served by
OpenRouter. Its model family differs from the first scorer (`openai/gpt-oss-120b`
on Groq) and from the generator (`llama3.2:3b`). It receives exactly the same
three batches as the first scorer, with the same rubric.

**Fabrication checker, if needed:** `nvidia/nemotron-3-ultra-550b-a55b:free`
via OpenRouter, a third model family.

**Decided before:** the second scorecard existed. The first scorecard (Groq)
was already frozen at commit 9a6cd79 and was not viewed.

**Amendment to D2 (same day, before any fabrication check):** the planned checker `nvidia/nemotron-3-ultra-550b-a55b:free` timed out on a minimal request. The checker is `nvidia/nemotron-3-super-120b-a12b:free`, same family, which answered it.

## D3 — Second scorer replaced again: Nemotron Super instead of Gemma (2026-09-16)

**What happened:** `google/gemma-4-31b-it:free` never accepted a batch. After
five retries over about ten minutes it still answered HTTP 429 with
`limit_source: upstream_provider_shared_pool` (Google AI Studio's shared free
pool), while accepting only minimal requests. It produced no score at all.

**Selection method:** candidate free models were probed with a request of the
same size as a real batch (about 3,900 prompt tokens of neutral filler, no
experiment content). Two accepted it: `nvidia/nemotron-3-super-120b-a12b:free`
(served by NVIDIA) and `nex-agi/nex-n2.5-pro:free` (served by Nex AGI).

**Deviation:** the second scorer is `nvidia/nemotron-3-super-120b-a12b:free`;
the fabrication checker, if one is needed, is `nex-agi/nex-n2.5-pro:free`. Four
distinct model families are now involved: generator (Meta), first scorer
(OpenAI open weights), second scorer (NVIDIA), checker (Nex AGI). The second
scorer receives the same three batches as the first.

**Decided before:** any second scorecard existed. The first scorecard was not
viewed.

## D4 — Second scorer's first scorecard refused for arithmetic; one full re-request (2026-09-16)

**What happened:** the budget of 4,000 output tokens truncated Nemotron Super's
reasoning; it was raised to 16,000 (same model, same batches, same rubric). The
scorer then returned eighteen cards, and ingestion refused them: in three cards
(all in batch 3) the declared total did not equal the sum of the components.
Ingestion checks this by design and no card was corrected by hand.

**What was seen:** only the refusal messages, which name three blind ids and
their declared and summed totals. No condition map was read; the first
scorecard (Groq) was still not viewed.

**Deviation:** the refused raw answers are archived under
`results/api_evaluations/rejected_arithmetic/` and the second scorer is asked
once more for all three batches, unchanged. If the new answer is again
inconsistent, the second scorer is declared unusable for this experiment and
the decision stays INCONCLUSIVE until another scorer is chosen by a rule
recorded beforehand. Totals are never recomputed from components.

**Decided before:** any usable second scorecard existed.

## D5 — Nemotron Super declared unusable; Nex N2.5 Pro becomes second scorer (2026-09-16)

**What happened:** under D4 the second scorer was asked again for all three
batches. Its new answer was again refused: one card's declared total did not
equal its component sum. By the rule recorded in D4, Nemotron Super is unusable
as a scorer for this experiment. Both refused answers are archived under
`results/api_evaluations/rejected_arithmetic/`.

**Deviation:** the second scorer is `nex-agi/nex-n2.5-pro:free` (Nex AGI), the
only other free model that accepted a full-size batch in the D3 probe. It
receives the same three batches with the same rubric, 16,000 output tokens,
and the same D4 rule: one full re-request on arithmetic refusal, then unusable.
The fabrication checker, if one is needed, becomes
`nvidia/nemotron-3-super-120b-a12b:free`; it produced no accepted scorecard and
is not a voter.

**What was seen:** only refusal messages. The condition map and the first
scorecard were not viewed.

**Decided before:** any usable second scorecard existed.
