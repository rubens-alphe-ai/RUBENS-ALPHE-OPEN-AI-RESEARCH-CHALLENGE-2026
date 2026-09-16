# EXP-REG-001 — Canonical State Regression Preservation

## Goal

Prevent a positive target metric from hiding a regression in the continuity
capabilities that make RA-PSI useful.

## Fixed regression capabilities

- reconstruct the mission from the supplied state;
- identify known failures and preserve uncertainty;
- propose one measurable next action;
- distinguish executed work from proposals;
- preserve provenance and rollback information.

## Procedure

1. Freeze the current canonical state hash and the candidate state hash.
2. Run the same blinded regression prompts against both states.
3. Score each capability with an independent evaluator packet.
4. Record every score and raw output hash in append-only provenance.
5. Any capability below its registered minimum vetoes final adoption.

No regression result authorizes a direct canonical write; only a separate
`FINAL_KEEP` state-delta step can do that.
