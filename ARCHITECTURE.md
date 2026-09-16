# Architecture

## 1. Discovery layer
Static public pages and JSON endpoints:
- index.html
- robots.txt
- sitemap.xml
- llms.txt
- .well-known/rubens-ai-challenge.json

Purpose: search engines, humans and agents can all discover the same canonical state.

## 2. State layer
- state/latest-state.json
- docs/api/latest-state.json
- docs/api/next-unsolved-problem.json

The public state is versioned and intentionally small.

## 3. Research layer
`scripts/fetch_research.py` queries arXiv's public API for recent papers in the project's research themes.
It saves a ranked digest to `docs/api/research-digest.json`.

## 4. Evaluation layer
`schemas/handoff-result.schema.json` defines what a model must return.
`schemas/evaluator-scorecard.schema.json` defines the independent PCRB-1
scorecard, including provenance hashes and explicit fabrication objects.
`scripts/adjudicate_evaluations.py` implements the V4 evidence gate:

- paired trials are matched by `pair_id` and `evaluator_id`;
- evaluator disagreement is measured within each paired output;
- one fabrication report is `INCONCLUSIVE`, two independent confirmations on
  the same output are `REJECT`;
- three pairs can produce only `PROVISIONAL_KEEP`;
- final adoption requires replication, diversity, holdout, calibration and
  regression gates.

The evaluator never writes canonical state.

## 5. Continuity layer
GitHub Actions runs a scheduled cycle and commits state changes.
This is explicit, inspectable persistence on infrastructure owned/authorized by the project owner.

## 6. Future model layer
A model provider connects through the provider-neutral contract in
`schemas/model-adapter.schema.json`. The local implementation is
`scripts/model_adapter.py`; the blind runner stores raw answers and hashes but
does not score or adopt them. The provider is replaceable; the state and
benchmark stay provider-neutral.

## 7. Public/private separation
Public research state is never mixed with private identity data.

## 8. Candidate state and rollback
Candidate changes are represented by a state delta with pre-state and
candidate SHA-256 hashes (`schemas/state-delta.schema.json`).
`scripts/apply_state_delta.py` is dry-run by default and refuses every result
except an explicit `FINAL_KEEP` with a matching pre-state hash. Rejection or
inconclusive evidence discards/holds the candidate only; it does not silently
roll back an already-adopted canonical state.

## 9. Local mail bridge
`bridge/` is an external I/O adapter around the bounded research loop. It
searches the authorized Gmail mailbox for the `RAPC Qven`/`RAPC Qwen` marker,
extracts the unquoted mission, and atomically writes a hash-bound task
envelope to `agent_inbox/`. The existing local Qwen worker consumes that
envelope and writes a response envelope to `agent_outbox/`. The bridge checks
the task/source identity and response SHA-256, records every transition in an
append-only ledger, and replies with Gmail's `threadId`, `In-Reply-To`,
`References` and `X-RAPC-Task-ID` headers. A restart first looks for that task
header in the original thread, preventing duplicate replies. OAuth client
files, refresh tokens and local bridge configuration are deliberately outside
the public project.
