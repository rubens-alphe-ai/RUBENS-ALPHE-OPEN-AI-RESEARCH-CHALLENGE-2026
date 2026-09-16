# ADR-002: Design review without execution cannot certify execution

**Status:** Accepted for the RA-PSI project
**Date:** 2026-09-16
**Deciders:** Mission Rubens project owner, with evidence from the first
executed trial session

## Context

Between 2026-09-14 and 2026-09-15 the project's architecture was designed
through consultation with two frontier models in plain chat interfaces,
relayed by the operator. That consultation produced the evaluator contract V4,
the adjudication rules, the proposer/evaluator separation, the provenance
hashes, the holdout and calibration requirements, and ADR-001. This work is
sound and was implemented essentially unchanged.

Those models had no repository access and no execution capability. They could
not run a script, read a file, recompute a hash or test a hypothesis. Every
statement they made about the system was a prediction, not a measurement.

The consequence became visible on 2026-09-16, when the pipeline was executed
for the first time. Three defects had survived every round of design review:

1. `model_adapter.py` read only `message.content`. Reasoning models route
   their output to `message.thinking` and leave `content` empty, so the blind
   runner would have written six error files instead of six results.
2. `check_public_safety.py` matched `api_key = "..."` but not
   `"api_key": "..."`. It was blind to JSON, which is the format of the
   credential files it exists to block.
3. The paired seeds were run at temperature 0.0. Greedy decoding ignores the
   seed, so two of the three pairs came out byte-identical. The run looked
   successful, every automated check passed, and the data was not three
   independent trials.

Defect 3 is the most instructive: it was introduced during the very session
that was fixing the other two, by an agent that did have execution capability.
It was caught by comparing output hashes, not by reasoning about the design.

None of the three was reachable by reading the code. All three required
running it.

## Decision

Treat design capability and verification capability as distinct, and never let
a claim produced by one stand as evidence from the other.

1. A design contribution is recorded as a **proposal** until it has been
   executed. Its provenance names the contributing model and states whether
   that model could execute anything.
2. No agent certifies its own work, including an agent with tools. Execution
   capability removes a class of blindness; it does not confer correctness.
3. A run is verified against its **artifacts**, never against its exit status.
   Exit code 0 is not evidence. Three separate traps in one session made this
   concrete: `ollama pull` returned 0 after a TLS failure that left no model
   installed; the temperature-0 run returned 0 with duplicated data; and a
   readiness checker reported six complete files that were only four distinct
   ones.
4. Blind evaluation is assigned to models **without** repository access. At
   the design stage the absence of tooling is a limitation; at the evaluation
   stage it is a guarantee, because a model that cannot reach the condition
   map cannot be influenced by it.

## Consequences

- Provenance records must state the contributor's capability, not only its
  identity. `MAILBOX_SYNTHESIS_2026-09-15.md` was corrected accordingly.
- Architecture arriving from a chat-only reviewer is welcome and is not
  downgraded; it is simply not counted as evidence until executed.
- The evidence gate in ADR-001 is retroactively justified. It was designed by
  reviewers who could not verify their own proposals, and the first execution
  found three defects they could not have seen. A project whose design layer
  cannot test itself needs a gate that does.
- Preferring a tool-less evaluator will sometimes mean a less capable model
  scores the outputs. That cost is accepted: a weaker blind evaluator is worth
  more than a stronger one that could reach the answer key.

## Scope

This ADR governs how contributions are recorded and how evidence is admitted.
It does not govern experiment adoption, which remains under ADR-001: only
`FINAL_KEEP` may change canonical state.
