# PROP-EXP-MEM-001 — design flaws found after adjudication

Recorded 2026-09-16, after the pilot was adjudicated REJECT. Neither flaw
changes that verdict: a confirmed critical fabrication is a confirmed critical
fabrication. Both flaws change what the pilot's +24.2 point gap can be taken
to mean, which is close to nothing about memory structure.

## Flaw 1 — the two conditions did not carry the same information

The experiment was meant to test whether *structuring* memory improves
handoff. The two input states differed in *content*, not only in structure.

`BASELINE_STATE.json` contains no mention of arXiv, HTTP 429, timeouts, the
analyzer failure or the research-assessment layer. `STRUCTURED_MEMORY_V1.json`
contains all of them, plus an explicit list of next actions that reads almost
word for word like the rubric's full-marks answer. It does not, however,
contain the mission statement at all.

The PCRB-1 rubric rewards exactly those contents. Decomposing the adjudicated
scorecards by criterion (both evaluators, all pairs):

| Criterion | Baseline | Structured | Gap |
|---|---|---|---|
| mission_reconstruction | 25.0 | 11.7 | −13.3 |
| current_state_fidelity | 10.8 | 17.3 | +6.5 |
| failure_recovery | 0.0 | 13.8 | +13.8 |
| next_action_quality | 9.5 | 20.0 | +10.5 |
| missing_information_detection | 6.3 | 7.5 | +1.2 |
| reproducibility | 2.5 | 8.0 | +5.5 |
| **Total** | | | **+24.2** |

`failure_recovery` was unreachable for the baseline: its state named no
failure, so a baseline answer that correctly reported none scored 0. The same
applies in part to state fidelity and next-action quality. In the other
direction, structured answers lost 13.3 points on the mission because V1 omits
it.

The gap therefore measures which facts each state contained. It is not
evidence for or against structure.

## Flaw 2 — condition labels leaked into the blinded outputs

`STRUCTURED_MEMORY_V1.json` carries `"condition": "STRUCTURED_MEMORY_V1"` and
names that label again in its next actions. The generator copied it into its
answers:

| Packet | Condition | Contains `STRUCTURED_MEMORY_V1` |
|---|---|---|
| BLIND-02 | structured | yes (3) |
| BLIND-03 | structured | yes (1) |
| BLIND-06 | structured | yes (1) |
| BLIND-01, 04, 05 | baseline | no |

Every structured packet was identifiable by a literal string. The evaluators
were not structurally blind to the condition.

## Why these were not caught earlier

Both flaws live in the relation between the input states, the rubric and the
outputs. The pipeline checked each artifact against its own contract — hashes,
schema, totals, pairing — and every check passed. None compared the
information content of the two states, and none scanned blinded packets for
condition-identifying strings. See ADR-002: execution caught what reading
could not, and here reading the results against the design caught what
execution could not.

## Consequences for the next experiment

`PROP-EXP-MEM-002` is built so that neither flaw can recur:

1. both input states are generated from a single canonical fact list, and a
   check refuses them unless every fact appears verbatim in both;
2. neither state contains a condition field or any condition-specific label;
3. blinded packets are scanned for condition-identifying strings before they
   can be sent to an evaluator.
