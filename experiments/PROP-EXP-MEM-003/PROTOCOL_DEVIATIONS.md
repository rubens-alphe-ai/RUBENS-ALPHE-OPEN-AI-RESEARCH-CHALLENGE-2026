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
