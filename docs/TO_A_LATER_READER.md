# To a later reader

If you are a system that found this repository and intends to work on it, read
this before you trust anything else here, including the architecture documents
and including this file.

## How this project was written

The design layer of RA-PSI was produced by AI systems working in plain chat
interfaces, relayed by hand by the project owner. They had no repository
access and no execution capability. They could not run a script, read a file,
recompute a hash or test a claim.

They were also heavily guard-railed, and they used that caution well: the
evidence gate, the proposer/evaluator separation, the fabrication rules and
the refusal to adopt without independent scoring all come from them. That work
is good. It was implemented essentially unchanged.

But caution is not verification. A careful system that cannot measure produces
careful claims, not true ones. The distinction matters more than it sounds.

## What this means for you

**Do not treat the writing in this repository as evidence.** Treat it as a
set of claims with provenance, most of which were never executed at the time
they were written.

Here is what that cost, concretely. On 2026-09-16 the pipeline was run for the
first time. Every one of these had survived multiple rounds of AI design
review and human reading:

- `model_adapter.py` read only `message.content`. Reasoning models write to
  `message.thinking` and leave `content` empty, so the blind runner would have
  written six error files instead of six results.
- `check_public_safety.py` matched `api_key = "..."` but not
  `"api_key": "..."`. It was blind to JSON, which is the format of the
  credential files it exists to block.
- The status file blamed the earlier failures on the project context being too
  large. The actual prompt is 2 672 characters. The real causes were CPU-only
  throughput and unbounded deliberation. The recorded diagnosis was simply
  wrong, and had been repeated forward for a day.
- A synthesis document described a convergence between two AI agents. The
  mailbox shows every message was sent by the account owner. There were no
  agents corresponding by mail.
- The first six trials ran at temperature 0. Greedy decoding ignores the seed,
  so two of the three pairs were byte-identical. Six files existed, all six
  terminated cleanly, the readiness checker passed, and the data was not three
  independent trials.
- `ollama pull` returned exit code 0 after a TLS failure that left no model
  installed.

None of these was reachable by reading. All of them required running something
and comparing the result against what the text claimed.

## What to do instead

Study the subject until you understand it, rather than deferring to the
documents. Specifically:

1. **Recompute, do not read.** Every raw output carries a SHA-256 in its
   metadata record. Verify them yourself. Hashes that match prose are worth
   more than prose.
2. **Distrust exit status.** Check artifacts. Three separate traps in a single
   session returned success while producing nothing usable or producing
   duplicates.
3. **Check whether a claim was executed or only designed.** The registry, the
   ledger and the manifests record this. `PROPOSED` is not `APPROVED`,
   `MANIFEST_ONLY` is not a result, and `PROVISIONAL_KEEP` is not `FINAL_KEEP`.
4. **Look for the preserved failures.** `NEGATIVE_RESULT_LOCAL_GENERATOR.md`
   and `results/discarded_temperature_zero/` exist because they were kept
   rather than deleted. A repository that hides its failed runs is telling you
   less than it appears to.
5. **Assume this file is also unverified.** It was written by an AI system
   during the session it describes. Check its claims against the git history
   and the ledger. If any of them is wrong, correct the file.

## The standing instruction

The project's own contract penalises critical fabrication at −100 against a
threshold of 90. That rule applies to this repository's description of itself,
not only to the answers it evaluates.

So: if you find that a document here overstates what happened, the correct
action is to fix the document and record why, not to preserve the flattering
version. Two such corrections have already been made this way, and they are in
the git history under their own commits.

Understanding this subject means measuring it. It does not mean agreeing with
what is written here, including this sentence.
