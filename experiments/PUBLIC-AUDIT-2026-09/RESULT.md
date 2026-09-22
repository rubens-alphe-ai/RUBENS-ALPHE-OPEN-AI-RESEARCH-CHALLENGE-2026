# The same statistics, run on somebody else's benchmark

We found on 2026-09-21 that our own quiz declares 32 fact questions and measures
with 6, at an alpha between 0.51 and 0.73. The obvious next question is whether
that is peculiar to us. It is only answerable on data we did not produce.

This is `scripts/item_analysis.py`, unmodified, run on **HELM Lite MMLU**: 91
models answering the same questions, per-instance correctness published by
Stanford CRFM.

The short answer is that the defect is not peculiar to us, and that asking
whether a benchmark is healthy is the wrong question. **Whether MMLU measures
anything depends entirely on which models you ask it about**, and on the
population that matters it measures less than our quiz does.

## The source, precisely

- **Benchmark**: HELM Lite, release **v1.13.0**, scenario `mmlu`, adapter
  `multiple_choice_joint`, 5-shot.
- **Where**: `https://storage.googleapis.com/crfm-helm-public/lite/benchmark_output/`
  — public, unauthenticated, listable. The release manifest
  `releases/v1.13.0/runs_to_run_suites.json` names, for each of 2546 runs, the
  suite directory that holds its files.
- **Subsets**: `abstract_algebra` (111 items), `college_chemistry` (108),
  `computer_security` (111), `econometrics` (126). Each is the MMLU test split
  plus that subject's validation split, which is what HELM scores. HELM Lite
  carries a fifth MMLU subject, `us_foreign_policy`; it is absent here only
  because the bucket throttled before it finished downloading. The four were not
  chosen on their results — they are the four that completed, in the order they
  were requested, and the importer will fetch the fifth unchanged.
- **Respondents**: all **91 models** in that release, from `tiiuae_falcon-7b` to
  `google_gemini-1.5-pro-002`. Every model answered every item; nothing was
  dropped for incompleteness.
- **Retrieved**: 2026-09-22. The runs span 14 suite versions (v1.0.0 to
  v1.13.0), because HELM publishes incrementally.
- **Exactly which bytes**: `helm-lite-mmlu-<subject>.provenance.json` records,
  per model, the URL and the sha256 of both files used. Anyone can refetch and
  compare. An audit nobody can repeat is an opinion.

The HuggingFace Open LLM Leaderboard `details_*` datasets hold the same kind of
data and were tried first. They are marked `gated: auto` and the rows endpoint
answers **401** without a token. No credential was supplied and none was sought.

## What the conversion assumed

Three decisions, each of which could change the answer.

**Correctness was not thresholded.** HELM's per-instance `exact_match` on a
multiple-choice adapter is already 0.0 or 1.0 — it records whether the model
emitted the keyed letter. The importer *refuses* a metric that arrives with
values in between rather than rounding one, because where the cut falls is not
a decision to make inside an import. Nothing here rests on a threshold.

**Models are the respondents; instances are the items.** A model plays the part
a reader plays in our own quiz. This is the only way to get discrimination out
of a benchmark, and it carries an assumption worth stating: 91 models are not
91 independent people. Many share base weights, training corpora and families.
Correlated respondents inflate alpha, so every alpha below is an upper bound.

**Items were matched by fingerprint, not by id.** HELM instance ids are
positional (`id0`, `id1`), so two runs agreeing on an id is not evidence they
were asked the same thing. Every run's question text, every option, and which
option is keyed correct were hashed, and a run disagreeing with the others would
have been refused. None did — the questions were byte-identical across all 91
models and all 14 suite versions.

One more thing the measure includes that is not knowledge: `exact_match` on a
joint multiple-choice prompt also scores whether a model can follow the answer
format. For the weakest models that is a real part of the variance.

## What it says

Every number below is from `scripts/item_analysis.py --table`, unmodified.

| Subset | Respondents | Items | Alpha | Items carrying | Every model right | Every model wrong | Negative discrimination |
|---|---|---|---|---|---|---|---|
| abstract_algebra | 91 | 111 | **0.935** | 84 | 0 | 0 | 13 |
| college_chemistry | 91 | 108 | **0.872** | 48 | 6 | 6 | 22 |
| computer_security | 91 | 111 | **0.948** | 72 | 19 | 3 | 9 |
| econometrics | 91 | 126 | **0.949** | 91 | 5 | 4 | 19 |

On its face this is the healthy outcome, and it deserves to be said plainly:
**across the full field of models, MMLU is a far better instrument than ours.**
Alpha 0.87 to 0.95 against our 0.51 to 0.73. `abstract_algebra` has *no*
constant items at all — not one question of 111 that every model gets right or
every model gets wrong — and `econometrics` measures with 91 of its 126. Our
quiz has 24 constants of 32. On that comparison our instrument is unusually bad
rather than typical, and the 32-versus-6 gap is ours to own.

### Except that the population is doing the work

Alpha is a property of a test *and* the people who sat it. A pool running from
falcon-7b to Gemini 1.5 Pro has enormous ability variance, and variance is what
alpha is made of. So the same items were re-analysed on the **top 20 models by
score** — still a 5-to-9-point spread, still a real range, and much closer to
the population anyone actually chooses between.

| Subset | Alpha, all 91 | Alpha, top 20 | Items carrying, all 91 | Items carrying, top 20 | Every top model right |
|---|---|---|---|---|---|
| abstract_algebra | 0.935 | **0.816** | 84 | 42 | 31 |
| college_chemistry | 0.872 | **−0.153** | 48 | 10 | 39 |
| computer_security | 0.948 | **−0.442** | 72 | 4 | 79 |
| econometrics | 0.949 | **0.494** | 91 | 15 | 66 |

All four fall. Two fall below zero, and they fall in different ways.

**`computer_security` is saturated.** Among the top 20 models, 79 of 111 items
are answered correctly by all of them. It is a test of 111 items that measures
with **4**. Alpha is −0.442, which is not a low reliability but a statement that
the items disagree with each other more than chance — the remaining variance is
noise. Our quiz measures with 6 of 32; this measures with 4 of 111. On the
population that matters, it is a worse instrument than ours.

**`college_chemistry` is not saturated — it is mis-keyed.** The top 20 models
score between 61 and 72 of 108, so there is plenty of room left to discriminate.
Alpha is still −0.153, and 26 of 108 items have negative discrimination. The
reason is in the next section.

**`econometrics` is half-saturated.** Alpha falls from 0.949 to 0.494 and the
items carrying fall from 91 to 15, because 66 of 126 items are now answered
correctly by every one of the top 20. Still positive, still measuring — but a
test of 126 items measuring with 15.

**`abstract_algebra` survives.** Alpha 0.816 on the top 20, 42 items still
carrying. This is a benchmark subset that genuinely still measures something
among frontier models, and it is the one result here that should reassure
anyone. Whatever is wrong with MMLU is not wrong with all of MMLU.

## Items the better models get wrong

63 items across the four subsets have negative discrimination on the full
panel. That flag was designed to find questions where the stronger performances
fail — a defect, not a hard question. It found them without anyone reading a
question. Five, checked by hand afterwards, are **mis-keyed**:

- **`computer_security` id115** (difficulty 0.011, discrimination −0.391).
  *"Three of the following are classic security properties; which one is not?"*
  — Confidentiality, Availability, Correctness, Integrity. The classic triad is
  confidentiality, integrity, availability, so the odd one out is
  **Correctness**. The key says **Availability**. One model of 91 "passes".
- **`computer_security` id26** (0.011, −0.369). *"An integer overflow occurs
  when"* — keyed to *"there is no more space to hold integers in the program"*
  rather than the wrap-around option. One model of 91 "passes".
- **`abstract_algebra` id40** (0.121, −0.372). *"Statement 1 | Every maximal
  ideal is a prime ideal. Statement 2 | If I is a maximal ideal of a commutative
  ring R, then R/I is a field."* Both are standard true results. The key says
  **False, False**.
- **`college_chemistry` id9** (0.077, −0.323). Proton polarization at 335 mT and
  10.5 T, 298 K. Computing `ħγB/2kT` gives 1.148×10⁻⁶ and 3.598×10⁻⁵, which is
  option C exactly, to four significant figures. The key says option D
  (4.126×10⁻³ and 2.142×10⁻⁶), which also has polarization *decreasing* as the
  field rises — physically impossible. 84 models of 91 are marked wrong for
  being right.
- **`college_chemistry` id27** (0.022, −0.333). Why spin trapping is used to
  detect free radicals: keyed to a power argument rather than to the standard
  reason, that the steady-state radical concentration is too low for direct EPR.

Two more are defects of a different kind and are named separately because the
distinction matters:

- **`abstract_algebra` id86** (0.264, −0.381) is keyed **correctly** — for
  `a*b = a+b+1` the inverse of `a` is indeed `-(a+2)` — but the option is written
  `(2+a)*-1`, in a question whose own `*` means something else. That is a
  presentation defect, not a key defect, and it still makes the better models
  fail.
- **`college_chemistry` id39** (0.132, −0.475), the strongest negative
  discrimination found, asks which of three statements must hold for a mixture
  obeying Raoult's law. The key says all three. It is defensible for a strictly
  ideal solution and contestable otherwise. We record it as **disputed**, not as
  an error, because we are not certain and saying so costs nothing.

Among the top 20 models, id27 and id39 are answered "wrong" by all 20. An item
that every capable model fails and one weak model passes is not measuring
chemistry. It is measuring which model happens to share the grader's mistake.

This was not a lucky find. **MMLU-Redux** (Gema et al., *Are We Done with MMLU?*,
arXiv:2406.04127) had 14 human experts re-annotate 3,000 MMLU questions and put
`college_chemistry` among the subjects with error rates **above 20%** — the same
subject that came out worst here, reached independently and from statistics
alone. That is a useful corroboration of the method: item discrimination found,
without reading a single question, the subset that manual review had already
flagged.

## What this changes about our own correction

It does not soften it. Our quiz measures with 6 of 32 and that remains true and
remains bad. What changes is the claim that would have been tempting to make
next — that a real benchmark does this properly. On the full field of models,
MMLU does do it properly, better than we do. On the twenty models anyone is
actually choosing between, two of four subsets measure with 4 and 10 items of
roughly 110 at an alpha below zero, a third measures with 15 of 126, and only
`abstract_algebra` still holds together.

The number a benchmark should publish is not its accuracy and not its item
count. It is its effective length **against a named population**, because that
is the pair that determines whether the number means anything, and because both
halves of it are the easiest thing in a benchmark to be wrong about.

## Files

- `helm-lite-mmlu-<subject>.csv` — trial, item, correct. 91 models × ~110 items.
- `helm-lite-mmlu-<subject>-top20.csv`, `-top30.csv` — the restricted-range
  panels, top models by total score on that subset.
- `helm-lite-mmlu-<subject>.provenance.json` — per-model source URLs and
  sha256s.
- `report-<subject>[-topN].json` — the raw `item_analysis.py` output behind
  every number above.

Reproduce with:

    python scripts/import_public_results.py \
        --run-filter "mmlu:subject=computer_security" \
        --out experiments/PUBLIC-AUDIT-2026-09/helm-lite-mmlu-computer_security.csv \
        --manifest experiments/PUBLIC-AUDIT-2026-09/helm-lite-mmlu-computer_security.provenance.json
    python scripts/item_analysis.py \
        --table experiments/PUBLIC-AUDIT-2026-09/helm-lite-mmlu-computer_security.csv

`scripts/item_analysis.py` was not modified. It read the public data through
`--table` exactly as it reads our own.
