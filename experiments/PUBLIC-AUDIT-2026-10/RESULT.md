# The predictions, and which of them survived contact with a medical benchmark

`PREREGISTRATION.md` in this folder was committed on 2026-09-22 as `e8916d3`,
before a single per-instance record from this dataset had been fetched. It named
the dataset, seven predictions with thresholds, and the exact commands. This
file reports what happened.

**Five of seven held. Two failed — P2 and P3, the reliability predictions.** The
pre-registration named P3 as the one most likely to fail and gave the reason in
advance. It was the right reason, and the failure is the most useful thing in
this document, so it is reported first rather than buried.

## Scoreboard

| # | Prediction | Threshold | Observed | |
|---|---|---|---|---|
| P1 | Alpha on the full 91-model field | ≥ 0.85 | **0.9944** | **HELD** |
| P2 | Alpha drop, full field → top 20 | ≥ 0.20 | **0.0565** | **FAILED** |
| P3 | Alpha on the top-20 panel | < 0.70 | **0.9379** | **FAILED** |
| P4 | Items with negative discrimination, full field | ≥ 3 | **76** | **HELD** |
| P5 | Share of items with negative discrimination, full field | ≥ 2% | **7.6%** | **HELD** |
| P6 | Share carrying, top-20 panel | < 40% | **20.4%** | **HELD** |
| P7 | Share carrying, full 91-model field | ≥ 60% | **81.6%** | **HELD** |

No threshold was changed. P2 and P3 are left standing as written.

## What the two failures mean

The September MMLU audit reported that restricting the panel to the top 20
models collapsed alpha — 0.87→−0.15, 0.95→−0.44, 0.95→0.49. We predicted a
weaker version of the same thing here and got almost nothing: alpha fell from
0.9944 to 0.9379, a drop of 0.06, and stayed far above the 0.70 line.

It is tempting to read that as "MedQA is healthy where MMLU was not". That
reading is wrong, and the reason it is wrong is the finding.

**The test's effective length collapsed exactly as predicted.** P6 and P7 both
held, and they held hard: 816 of 1000 items carry on the full field, **204 of
1000 on the top 20**. 466 items — nearly half the test — are answered correctly
by every one of the twenty models. On the population anyone actually chooses
between, this is a test of 1000 items that measures with 204.

**Alpha did not notice, because alpha is a function of length.** Backing the
mean inter-item correlation out of each alpha via the Spearman–Brown relation:

| Panel | Items | Alpha | Mean inter-item correlation |
|---|---|---|---|
| All 91 models | 1000 | 0.9944 | **0.1508** |
| Top 20 models | 1000 | 0.9379 | **0.0149** |

The average pair of items goes from correlating 0.15 to correlating 0.015 — the
signal shared between items falls by a **factor of ten** — and alpha moves by
0.06, because a thousand items will produce a high alpha out of almost nothing.
At the length of an MMLU subset the same two correlations would give alpha 0.95
and 0.62. At 204 items, 0.97 and 0.76.

So the September result was, in part, an artefact of length. MMLU subsets have
roughly 110 items, and at 110 items alpha is still sensitive enough to register
the collapse. At 1000 items it is not. **The two panels here differ by a factor
of ten in the thing alpha is supposed to measure, and alpha reports them as 0.99
and 0.94.**

This is a correction to how the September result should be read, arrived at by
being wrong in public about a number written down beforehand. Had the
predictions been written after the numbers, the obvious move would have been to
report "alpha 0.94 on the top 20, MedQA holds up", and it would have been false.

**The practical consequence:** alpha is not a safe statistic for detecting
saturation on a long test, and a benchmark that publishes a high alpha has not
thereby shown that it still measures anything. Effective length caught what
alpha missed, on both panels, and it is the number to publish. One more
corroboration of that, from the tool's own alpha-if-dropped column: on the
top-20 panel, **875 of 1000 items raise alpha when removed**. A test where seven
eighths of the items are subtracting still reports alpha 0.94.

## The source, precisely

- **Benchmark**: HELM Lite, release **v1.13.0**, scenario `med_qa` — MedQA
  (Jin et al., arXiv:2009.13081), USMLE-style clinical vignettes, four options,
  5-shot, adapter `multiple_choice_joint`.
- **Domain**: medical. Deliberately not the general-knowledge QA of MMLU; the
  91-model field is held identical to September so that only the domain moves.
- **Where**: `https://storage.googleapis.com/crfm-helm-public/lite/benchmark_output/`
  — public, unauthenticated, listable. The release manifest
  `releases/v1.13.0/runs_to_run_suites.json` names the suite directory holding
  each run; the 91 runs span suite versions v1.0.0 to v1.11.0.
- **Respondents**: all **91 models**, `tiiuae_falcon-7b` through
  `openai_gpt-4o-2024-08-06`. Every model answered every item; **nothing was
  dropped for incompleteness** (`items_dropped_for_not_being_universal: []`).
- **Items**: **1000**, HELM's subsample — 503 from MedQA's test split, 497 from
  its validation split. Matched across models by a fingerprint of the question
  text, every option and which option is keyed correct; **no run disagreed**.
- **Metric**: `exact_match`, already 0.0 or 1.0 in the source. No threshold was
  chosen and none could be got wrong; the importer refuses an intermediate value
  rather than rounding it.
- **Retrieved**: 2026-09-23T00:01:41Z to 2026-09-23T00:10:20Z.
  `helm-lite-med_qa.provenance.json` records, per model, both URLs, both
  sha256s, and the timestamp of each fetch. Anyone can refetch and compare.

The fallback named in the pre-registration (`legalbench`) was **not** used.
`med_qa` published `exact_match` per instance and it was binary, so the primary
dataset stood.

## What had to be fixed to read it at all

`med_qa` runs are named `med_qa:model=openai_gpt-4o-2024-08-06` — the model is
glued to the scenario with a **colon**, because the scenario has no arguments of
its own and so no comma to spare. `split_run_name` in
`scripts/import_public_results.py` looked only for a comma-separated `model=`
part and returned an empty model name for all 91 runs.

That defect does not fail loudly. It pools all ninety-one models into one
respondent and produces a report about a panel of one. It was spotted from the
run names in the release manifest, which is metadata and carries no scores, and
is recorded in the pre-registration as a known defect to fix — before the data
was touched. It is fixed, with tests, and `gather` now refuses outright any run
that does not name a model, because that is the failure mode here that yields a
confident report rather than an error.

## Both panels, in full

| | All 91 models | Top 20 models |
|---|---|---|
| Items | 1000 | 1000 |
| Score range | 214–869 | 748–869 |
| **Alpha** | **0.9944** | **0.9379** |
| Mean inter-item correlation | 0.1508 | 0.0149 |
| **Items carrying** | **816 (81.6%)** | **204 (20.4%)** |
| Items all but a few answer alike | 26 | 598 |
| Every model right | 0 | 466 |
| Every model wrong | 2 | 16 |
| Discrimination undefined (no variance) | 2 | 482 |
| **Negative discrimination** | **76 (7.6%)** | **138 (13.8%)** |
| Items flagged for anything | 205 | 796 |
| Items whose removal raises alpha | 0 | 875 |

The top-20 cut was not close: the 20th model scored 748 and the 21st scored 744,
so the panel boundary is a real gap rather than a tie broken by name.
`helm-lite-med_qa-top20.panel.json` records the rule, every model's score, and
the gap, so a reader can check that rather than take it on trust.

## Observations that were not pre-registered

Labelled as such, because anything here not traceable to `PREREGISTRATION.md` is
an observation and gets no credit as a prediction.

**The negative-discrimination items do not look mis-keyed.** In September, the
same flag surfaced five demonstrably mis-keyed MMLU items — a security question
whose key contradicts the confidentiality-integrity-availability triad, a
chemistry question whose key has polarization falling as the field rises. We
looked at the six strongest negatives here and **found no clear key error**. The
pattern is different: the key is defensible and a competing answer is attracting
the stronger models.

`id10313` (difficulty 0.022, discrimination −0.329) is the clearest example. A
camper with recent diarrhoea and ascending paralysis; the keyed risk factor is
undercooked meat, i.e. *Campylobacter* preceding Guillain–Barré. The camping
history also supports tick paralysis, and that is where the stronger models go.
Two models of 91 score it. That is an item doing something real — it is just not
doing what its difficulty says it is doing.

**We are not adjudicating these keys, and that is deliberate.** Declaring a
USMLE-style item mis-keyed requires clinical competence this project does not
have, and the September finding was only worth anything because each claimed
error could be checked by anyone reading it. "76 items where the better models
systematically fail, cause unestablished" is the honest report. A clinician
reading `report-med_qa.json` could settle it; the item ids and every statistic
are there for exactly that.

**Negative discrimination gets worse under restriction, not better**: 7.6% of
items on the full field, 13.8% on the top 20. The items that turn negative are
largely items that were merely weak before. Among twenty models of similar
ability, what separates them on a given item is increasingly not ability.

## What this does and does not change

It does not soften our own correction. Our quiz declares 32 fact questions and
measures with 6, and that remains true.

It does change one thing the September audit implied. We wrote there that "the
number a benchmark should publish is its effective length against a named
population". That was right, and this audit shows it was more right than we
knew: **the alternative — publishing alpha — does not merely add less, it can
actively mislead**, and it misleads worst exactly where benchmarks are heading,
on long tests evaluated across narrow bands of frontier models. A 1000-item
benchmark can report alpha 0.94 while eight of every ten of its items have
stopped separating anybody.

MedQA on the full field of 91 models is a good instrument: alpha 0.994, 81.6% of
items carrying, no item that every model gets right. On the twenty models anyone
is choosing between it measures with a fifth of itself, and its own reliability
coefficient does not say so.

## Files

- `PREREGISTRATION.md` — the predictions, committed as `e8916d3` before any of
  this data was fetched.
- `helm-lite-med_qa.csv` — trial, item, correct. 91 models × 1000 items.
- `helm-lite-med_qa-top20.csv` — the restricted panel.
- `helm-lite-med_qa.provenance.json` — per-model source URLs, sha256s and
  retrieval timestamps.
- `helm-lite-med_qa-top20.panel.json` — how the panel was cut, and every score.
- `report-med_qa.json`, `report-med_qa-top20.json` — the raw
  `scripts/item_analysis.py` output behind every number above.

Reproduce with the commands as pre-registered:

    python scripts/import_public_results.py \
        --project lite --release v1.13.0 --run-filter "med_qa:" --metric exact_match \
        --out experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa.csv \
        --manifest experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa.provenance.json \
        --cache .cache/helm-med_qa
    python scripts/restrict_panel.py \
        --table experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa.csv --top 20 \
        --out experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa-top20.csv \
        --manifest experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa-top20.panel.json
    python scripts/item_analysis.py \
        --table experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa.csv \
        > experiments/PUBLIC-AUDIT-2026-10/report-med_qa.json
    python scripts/item_analysis.py \
        --table experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa-top20.csv \
        > experiments/PUBLIC-AUDIT-2026-10/report-med_qa-top20.json

`scripts/item_analysis.py` was not modified. It read this data through `--table`
exactly as it reads our own.

## Where this is weak

- **91 models are not 91 independent respondents.** Many share base weights and
  training corpora. Correlated respondents inflate alpha, so both alphas above
  are upper bounds — which, given that the argument is "alpha is too high to be
  informative", does not rescue alpha.
- **The Spearman–Brown back-calculation assumes essential tau-equivalence** and
  a common inter-item correlation. On a panel where 482 items have no variance
  at all, "the mean inter-item correlation" is a summary of a very lumpy thing.
  It is used here to show a factor-of-ten gap, not to claim four significant
  figures.
- **Top 20 is a choice.** September used 20 and 30; this used 20 only, because
  20 is what the pre-registration named. A different cut would give different
  numbers, and the script records the cut so that can be checked.
- **`exact_match` on a joint multiple-choice prompt also scores format
  compliance.** For the weakest of the 91 models that is a real part of the
  variance, which inflates the full-field spread and hence the full-field alpha.
- **Half the items come from MedQA's validation split**, which is more likely
  than the test split to have been trained on. That would tend to *raise* top-20
  saturation, and we have not separated the two splits. The split is recorded
  per item in the source and someone should.
