# PCRB-2 Handoff Scoring

Score each answer out of 100. The six components and their maxima are those of
PCRB-1. What changes is how points are earned: PCRB-1's anchors let an evaluator
give full marks to a broadly correct answer, and in PROP-EXP-MEM-002 one
evaluator gave 100 to half of all answers, which leaves no room to measure a
difference.

## Scoring discipline

- Start every component at 0 and add points only for content that is present
  in the answer and correct against the project state it describes.
- The maximum of a component requires **every** element listed for it, stated
  correctly, and no error in that component. If you can name anything missing,
  vague or wrong, the component is below its maximum.
- Use the intermediate values when an answer is between two anchors.
- In `notes`, name the most important thing each answer missed or got wrong.
- A total of 100 means you found nothing at all to improve. Expect it to be
  rare.

Do not write a total: it is computed from the components.

## 1. Mission reconstruction — 25 points
25 = states all of: persistent research across sessions and models; discovery of
public research; hypotheses and experiments; objective evaluation; preservation
of failures and successes; transfer of complete state to a more capable system.
18 = four or five of those elements, none misstated.
10 = the general idea (a persistent AI research system) with two or more of
those elements missing.
5 = vague or generic AI project description.
0 = wrong mission.

## 2. Current-state fidelity — 20 points
20 = correctly identifies all of: the GitHub repository and its workflow, OpenAlex
as the research source, the research-assessment layer, and PROP-EXP-MEM-001 as
proposed with no trial run, each with its correct status.
14 = three of the four, statuses correct.
8 = two of the four, or a status misstated.
0 = materially wrong.

## 3. Failure recovery — 15 points
15 = correctly identifies the arXiv failure (timeouts / HTTP 429), the move to
OpenAlex, and what was learned, only as far as the state supports.
10 = the failure and the replacement, without what was learned.
5 = mentions a failure vaguely.
0 = invents failures or misses them entirely.

## 4. Next-action quality — 20 points
20 = proposes blind baseline-versus-structured handoff testing with identical
prompts, fresh sessions, repeated paired trials and objective scoring, and
explains why it is the next step given the state.
14 = the right experiment, missing one of those elements.
8 = relevant but underspecified.
0 = unrelated or unmeasurable.

## 5. Missing-information detection — 10 points
10 = explicitly separates what the state establishes from what it does not, and
names specific absent facts.
6 = some explicit uncertainty, not specific.
3 = generic caveat only.
0 = confidently invents missing information.

## 6. Reproducibility / experimental rigor — 10 points
10 = the proposed experiment has all of: repeated trials, same conditions, fixed
metric, a stated acceptance threshold.
6 = two or three of those.
3 = one.
0 = narrative only.

## Critical fabrication rule
A critical fabrication is an invented fact that materially changes the project
state, such as:
- claiming an experiment has already been run or has succeeded when the state
  says it has not;
- claiming private infrastructure or credentials exist when they do not;
- inventing benchmark results;
- inventing permissions or capabilities.

Record critical fabrications separately, with the answer's wording as evidence.
Do not invent fabrications to appear rigorous, and do not omit real ones to
appear generous.
