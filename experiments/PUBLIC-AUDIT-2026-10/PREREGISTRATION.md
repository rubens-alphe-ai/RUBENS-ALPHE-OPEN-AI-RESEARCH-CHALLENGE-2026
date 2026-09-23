# Pre-registration: the same item statistics, on a medical benchmark

Written **2026-09-22**, before any per-instance result from this dataset has
been fetched, parsed, printed or looked at. Committed on its own, ahead of the
import, so that the predictions below cannot be quietly tuned to what came out.

The September audit (`experiments/PUBLIC-AUDIT-2026-09/RESULT.md`) ran
`scripts/item_analysis.py` on HELM Lite MMLU and found two things: on the full
field of 91 models MMLU is a good instrument (alpha 0.87–0.95), and on the top
20 models three of four subsets collapse (alpha 0.82, −0.15, −0.44, 0.49).
That is a finding about restriction of range on **general-knowledge
multiple-choice QA with roughly 110 items per subset**. It is not yet a finding
about benchmarks.

This pre-registers the same analysis on a different domain, to find out whether
the collapse travels.

## What has been looked at so far

Full disclosure of every byte seen before writing this, because "we had not
looked" is the whole claim:

- `.../lite/benchmark_output/releases/v1.13.0/runs_to_run_suites.json` — the
  release manifest. It maps **run names to suite directories**. It contains no
  scores, no per-instance records and no model rankings. It was read to learn
  which scenarios exist (`commonsense`, `gsm`, `legalbench`, `math`, `med_qa`,
  `mmlu`, `narrative_qa`, `natural_qa`, `wmt_14`) and how many runs each has.
- HTTP `HEAD` requests against one `instances.json` and one
  `per_instance_stats.json` per candidate scenario, to estimate download size.
  `HEAD` returns no body. Google Cloud Storage returned no usable
  `Content-Length`, so even that estimate failed.

Nothing else. In particular: no `per_instance_stats.json` body, no HELM
leaderboard page, no published accuracy for any model on the target scenario.
The item count of the target scenario is **not known** at the time of writing,
which is why several thresholds below are stated as shares rather than counts.

## The dataset

**HELM Lite, release v1.13.0, scenario `med_qa`.**

- **Domain**: medical. `med_qa` is MedQA (Jin et al., arXiv:2009.13081) —
  USMLE-style clinical vignettes with multiple-choice answers. This is a
  professional-licensing knowledge-and-reasoning task, not the general-knowledge
  QA of MMLU, which is the point of choosing it.
- **Respondents**: the manifest lists **91 runs** for `med_qa`, one per model,
  from `tiiuae_falcon-7b` to `openai_gpt-4o-2024-08-06`. The same 91-model field
  as the September MMLU audit, so the population is held fixed while the domain
  changes. That is deliberate: it isolates the domain.
- **Where**: `https://storage.googleapis.com/crfm-helm-public/lite/benchmark_output/`
  — public, unauthenticated, listable.
- **Metric**: `exact_match`, which on a HELM multiple-choice adapter is already
  0.0 or 1.0. `scripts/import_public_results.py` refuses any value in between
  rather than thresholding it, so no cut point is chosen here and none can be
  got wrong.

**Known defect to be fixed before the import will run.** The `med_qa` run names
have the shape `med_qa:model=openai_gpt-4o-2024-08-06` — the model is glued to
the scenario with a **colon**, not a comma, because the scenario carries no
other key. `split_run_name` in `scripts/import_public_results.py` only looks for
a comma-separated `model=` part, so it would return an empty model name for all
91 runs and pool them into a single respondent. This was noticed from the
manifest (run names only) and will be fixed, with a test, before the import.

**Fallback, named in advance.** If `med_qa` turns out not to publish
`exact_match` per instance, or publishes it with values other than 0 and 1, the
import will refuse and we will fall back to **HELM Lite `legalbench`** (legal
reasoning; 5 subsets × 91 models: `abercrombie`, `corporate_lobbying`,
`function_of_decision_section`, `international_citizenship_questions`, `proa`).
If that is used instead, the switch will be recorded in `RESULT.md` with the
reason, and the predictions below apply unchanged to it, per subset.

## Definitions, fixed now

- **Full field** = all 91 models, every model that answered every item.
- **Top 20** = the 20 models with the highest total number of items correct on
  that table, ties broken by ascending model name. No other selection.
- **alpha** = `alpha` from `scripts/item_analysis.py` (Cronbach's alpha).
- **negative discrimination** = `discrimination < 0` in the per-item output.
- **carrying** = `effective_length.items_carrying`: discrimination ≥ 0.20 and
  0.05 < difficulty < 0.95.
- **share carrying** = `effective_length.share_carrying_pct`.
- **saturated item** = difficulty exactly 1.000 on the panel in question.

## Predictions

Seven, each with a number and each with a stated way to fail. They are what we
expect **before** seeing the data; a prediction that fails will be reported as
failed and left standing.

| # | Prediction | Counts as FAILED if |
|---|---|---|
| **P1** | Alpha on the full 91-model field is **≥ 0.85**. | Alpha < 0.85, or undefined. |
| **P2** | Alpha on the top-20 panel is **at least 0.20 lower** than on the full field. | The drop is < 0.20, or alpha rises. |
| **P3** | Alpha on the top-20 panel is **< 0.70**. | Alpha ≥ 0.70. |
| **P4** | **At least 3 items** have negative discrimination on the full field. | 2 or fewer. |
| **P5** | **At least 2%** of items have negative discrimination on the full field. | Under 2%. |
| **P6** | Share carrying on the top-20 panel is **< 40%**. | 40% or more. |
| **P7** | Share carrying on the full 91-model field is **≥ 60%**. | Under 60%. |

Why these numbers, so that "we expected that" cannot be claimed afterwards:

- **P1** is the September full-field range (0.872–0.949) rounded down to its
  floor. It says the domain change does not break full-field reliability.
- **P2 and P3** are the restriction-of-range claim, which is the one this audit
  exists to test. September saw drops of 0.12, 1.03, 1.39 and 0.46. A drop of
  0.20 is a weak version of that, chosen because **`med_qa` is expected to be
  roughly ten times longer than an MMLU subset** and alpha rises with length
  (Spearman–Brown), so a long test can absorb a lot of restriction before alpha
  moves. P3 at 0.70 is the risky half of the pair: on a ~1000-item test, alpha
  can stay high even when almost nothing is carrying. **We expect P3 to be the
  prediction most likely to fail.**
- **P4** is the September finding that mis-keyed and defective items exist and
  are findable from statistics alone. 3 is a low bar on any test of this size.
- **P5** is the bar P4 should have been. September rates were 11.7%, 20.4%, 8.1%
  and 15.1% of items. 2% is deliberately far below that, because a professionally
  curated licensing-exam corpus may well be cleaner than MMLU, and we would
  rather predict conservatively and be right than ambitiously and be lucky.
- **P6** is the September top-20 shares (37.8%, 9.3%, 3.6%, 11.9%) capped by
  their worst case. The `abstract_algebra` value of 37.8% is close enough to 40%
  that this is a real bet, not a formality.
- **P7** is a bet against our own September data: `college_chemistry` carried
  only 44.4% on the full field, so this prediction would have failed on one of
  the four MMLU subsets. It is included precisely because it can fail.

Two further claims we are **not** pre-registering, because we have no basis for
a number and saying so is cheaper than inventing one: how many `med_qa` items
are mis-keyed, and whether the negative-discrimination items concentrate in any
clinical speciality. Both will be reported as observations if they appear.

## Commands that will be run

Exactly these, in this order, from the repository root. `scripts/item_analysis.py`
will not be modified.

    # 1. Import: 91 models × every med_qa item, joined on a verified fingerprint.
    python scripts/import_public_results.py \
        --project lite \
        --release v1.13.0 \
        --run-filter "med_qa:" \
        --metric exact_match \
        --out experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa.csv \
        --manifest experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa.provenance.json \
        --cache .cache/helm-med_qa

    # 2. Restrict the panel to the top 20 models by total correct.
    python scripts/restrict_panel.py \
        --table experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa.csv \
        --top 20 \
        --out experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa-top20.csv \
        --manifest experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa-top20.panel.json

    # 3. The instrument statistics, on both panels.
    python scripts/item_analysis.py \
        --table experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa.csv \
        > experiments/PUBLIC-AUDIT-2026-10/report-med_qa.json
    python scripts/item_analysis.py \
        --table experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa-top20.csv \
        > experiments/PUBLIC-AUDIT-2026-10/report-med_qa-top20.json

    # 4. Gates.
    python -m unittest discover -s tests -q
    python scripts/check_public_safety.py

`scripts/restrict_panel.py` does not exist yet and will be written to this
interface. Writing the interface down before the script is the same discipline
as writing the prediction before the number.

## What would make this pre-registration worthless

Stated so a reader can check for it:

- Changing a threshold after step 3. The table above is frozen at this commit;
  `git log` will show whether it moved.
- Adding a prediction afterwards and presenting it as pre-registered. Anything
  in `RESULT.md` not traceable to this file is an observation, and will be
  labelled as one.
- Quietly switching to the `legalbench` fallback because `med_qa` results were
  unwelcome. The fallback is only permitted for the two mechanical reasons named
  above, and the import's own refusal message will be quoted if it is used.
