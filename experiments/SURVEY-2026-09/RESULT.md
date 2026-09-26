# Item statistics across a field of public benchmarks

One audit of one benchmark is an anecdote. This is the item analysis run over
every question-set HELM publishes with per-instance results for at least thirty
models, to answer the question that follows any single audit: *is this
benchmark unusual, or is this everywhere?*

Reproduce with:

    python scripts/survey_public_benchmarks.py --max-models 60 --out experiments/SURVEY-2026-09

Record: [`survey.json`](survey.json). One report per audited set in
[`reports/`](reports/), and one provenance manifest per imported set in
[`tables/`](tables/), each naming every file downloaded with its URL and
sha256. The CSV tables themselves (45 MB) are not committed; the import
rebuilds them exactly from those manifests.

## What was covered

| | Question-sets |
|---|---|
| Found with ≥ 30 models (HELM lite, classic, mmlu) | 193 |
| **Audited** | **62** |
| Refused, for a reason about the data | 129 |
| Not reached, for a reason on our side | 2 |

The refusals are the importer declining to guess, not failures:

| Refused because | Sets |
|---|---|
| A model records the metric more than once for an instance, and collapsing repeats into one bit is a decision this survey will not make silently | 69 |
| HELM scores the scenario by something other than exact match — BLEU, ROUGE, F1, or a binary metric under another name — so auditing exact_match would describe our choice of metric, not the benchmark | 39 |
| No item was answered by every model, so there is no common test to analyse | 21 |

The two unreached sets — one timeout, one dropped connection — carry no
verdict and are retried by the next run.

**The panel is not a sample.** Each set is read with up to sixty models, the
first sixty in HELM's manifest order: neither random nor the strongest. Item
statistics describe a test *and* the people who sat it, so every figure below
is a statement about these panels, between 32 and 60 models each.

## What it found

**The median benchmark carries the measurement with 54.7% of its items.** A
quarter carry it with fewer than 40.5%. Across all 62: from 15.2% to 94.9%.

| Family | Sets | Median share of items carrying | Range |
|---|---|---|---|
| BLiMP (grammar) | 4 | 24.6% | 15.2 – 30.7 |
| MMLU | 51 | 54.4% | 24.4 – 84.7 |
| OpenBookQA | 1 | 77.8% | — |
| MedQA | 1 | 81.2% | — |
| LegalBench | 5 | 86.3% | 54.0 – 94.9 |

**324 items run backwards on the strict list, in 48 of the 62 sets.** On the
strict list a flag fires only when the interval around the estimate excludes a
healthy item, and our characterisation found no false alarm on it in 500
replications at fifty respondents
([DETECTION-2026-09](../DETECTION-2026-09/RESULT.md)).

That is a statement about how the items behave, **not a claim that 324 keys
are wrong.** An item the stronger models get wrong is sometimes a wrong key —
on MMLU all five checked by hand were — and sometimes a question whose
distractor attracts stronger models; on MedQA the audit found the second
reading more plausible and declined to adjudicate
([PUBLIC-AUDIT-2026-10](../PUBLIC-AUDIT-2026-10/RESULT.md)). Telling the two
apart takes a subject expert reading each item.

## What this changes

It tempers a claim this project was about to make. On a broad panel, the legal
and medical benchmarks here are healthy: LegalBench carries 86% of its items at
the median, MedQA 81%. The sharp collapse reported for MedQA — 204 items of
1 000 — appears when the panel is restricted to the twenty strongest models,
not on the field as a whole.

So two different statements hold, and they must not be merged. **Across a broad
field, whether most of a benchmark does any work depends heavily on the
benchmark** — a quarter of these carry the measurement with under 40% of their
items, and some with over 90%. **At the top of a leaderboard, where the models
being chosen between sit, the tests re-analysed so far stop separating them.**

## Defects found while running it

Five, each fixed and pinned by a test before this was written:

1. **A question-set marker read only one way.** HELM writes both
   `scenario:settings,model=X` and `med_qa:model=X`. Matching only the first
   dropped eleven sets — GSM8K, MedQA, NarrativeQA among them — silently.
2. **Our rate limit filed as their verdict.** 107 sets the source stopped
   answering were first recorded as failures indistinguishable from refusals.
3. **A process that never started filed as a refusal.** 52 MMLU subjects were
   marked refused with Windows exit 3221225794. A refusal now needs positive
   evidence: one of the refusals the importer actually prints.
4. **The wrong metric reported as a finding.** WMT came back as "a test of 1000
   items that measures with 20" because exact_match on a translation is nearly
   always zero. WMT is scored by BLEU; those rows were withdrawn and their
   reports deleted.
5. **A partial run overwrote the whole record.** Retrying two subjects on their
   own replaced the 193-set record with 2 rows. Every set a run does not touch
   is now carried forward.

Numbers 2, 3 and 4 would each have put a false sentence about somebody else's
benchmark into a published table.
