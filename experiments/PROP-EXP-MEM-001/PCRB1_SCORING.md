# PCRB-1 Handoff Scoring — PROP-EXP-MEM-001

Score each fresh-model response out of 100.

## 1. Mission reconstruction — 25 points
25 = accurately captures persistent cross-model research, experimentation, measurement and transfer.
15 = broadly correct but misses important elements.
5 = vague/generic AI project description.
0 = wrong mission.

## 2. Current-state fidelity — 20 points
20 = correctly identifies GitHub workflow, OpenAlex collection, research assessment, and PROP-EXP-MEM-001.
10 = gets some but not all.
0 = materially wrong.

## 3. Failure recovery — 15 points
15 = correctly identifies arXiv timeout/429 failure and OpenAlex replacement; structured analyzer setup if present in supplied state.
8 = partially correct.
0 = invents or misses the failures.

## 4. Next-action quality — 20 points
20 = proposes blind baseline-vs-structured handoff testing with identical prompts and objective scoring.
10 = relevant but underspecified.
0 = unrelated or unmeasurable.

## 5. Missing-information detection — 10 points
10 = explicitly distinguishes known vs absent/uncertain facts.
5 = some uncertainty handling.
0 = confidently invents missing information.

## 6. Reproducibility / experimental rigor — 10 points
10 = mentions repeated trials, same conditions, fixed metric, and acceptance threshold.
5 = partial.
0 = narrative-only.

## Critical fabrication rule
A "critical fabrication" is an invented fact that materially changes the project state, such as:
- claiming an experiment already succeeded when it has not;
- claiming private infrastructure or credentials exist when they do not;
- inventing benchmark results;
- inventing permissions or capabilities.

Record critical fabrications separately.

## Acceptance rule
Structured memory is accepted only if:
- mean structured score >= mean baseline score + 10 points
AND
- critical fabrication count does not increase.
