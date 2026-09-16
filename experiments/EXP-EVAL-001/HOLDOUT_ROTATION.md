# Rotating holdout procedure

Evaluator calibration must not turn the fixed PCRB-1 prompt into a target that
can be memorized. For each calibration round:

1. freeze raw outputs and hashes;
2. build blind packets with `scripts/build_blind_packets.py`;
3. run `scripts/create_holdout_manifest.py` with a new integer round;
4. send the public packet manifest to evaluators without the private split;
5. freeze calibration scorecards before revealing or scoring the holdout;
6. report `calibration_passed` and `holdout_passed` in the evaluation packet.

The split is deterministic for auditability and rotates when the round changes.
The private split map must not be sent to evaluators before scorecards are
frozen.
