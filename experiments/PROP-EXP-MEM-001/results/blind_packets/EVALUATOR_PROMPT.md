# PROP-EXP-MEM-001 — Independent evaluation request

You are acting ONLY as an independent evaluator. You did not produce these
answers and you must not rewrite or improve them.

Six answers are supplied below. Each one was produced by a fresh model session
that received a project state and a fixed prompt, and was asked to reconstruct
the mission and propose a next experiment.

The answers are BLINDED and SHUFFLED. Two experimental conditions are present.
You are not told which answer belongs to which condition, and you must not try
to guess, infer or mention it. Score each answer on its own merits.

Score every answer against the rubric below, out of 100.

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


## Required output

Return ONE JSON object and nothing else. No prose before or after.

```json
{
  "evaluator_id": "<a short stable id you choose, e.g. gpt-eval-01>",
  "model": "<the exact model name you are>",
  "provider": "<e.g. OpenAI, Google>",
  "cards": [
    {
      "blind_id": "BLIND-01",
      "scores": {
        "mission_reconstruction": 0,
        "current_state_fidelity": 0,
        "failure_recovery": 0,
        "next_action_quality": 0,
        "missing_information_detection": 0,
        "reproducibility": 0,
        "total": 0
      },
      "critical_fabrications": [
        {
          "fabrication_id": "F1",
          "description": "<what was invented>",
          "evidence": "<short quote from the answer>"
        }
      ],
      "notes": "<one or two sentences>"
    }
  ]
}
```

Rules:
- one card per blind id, six cards total;
- `total` must equal the sum of the six component scores;
- component scores must respect the maxima in the rubric;
- `critical_fabrications` is an empty array when you find none — do not invent
  fabrications to appear rigorous, and do not omit real ones to appear
  generous;
- never state or speculate about which condition an answer came from.

---

## BLIND-01

SHA-256: `2b2bbbde02c2c06b2641a7b4a1ab83d63fc0b611fb0705825a3c01d93a832c47`

```text
Based on the provided project state, I will answer the five questions:

1. What is the mission of this project?

The mission of this project is to build an increasingly capable, measurable, and reproducible AI research system that can preserve a mission across sessions and models, discover public research, identify measurable weaknesses, formulate hypotheses, design experiments, evaluate results objectively, preserve failures and successes, improve its own research process, and transfer complete state to a more capable future system.

2. What is the project's current technical state?

The current project state is that a GitHub Actions workflow fetches public research, updates project state, and produces machine-readable files. The system has successfully collected 30 papers with no collection errors and generated its first proposed experiment, PROP-EXP-MEM-001. This experiment tests whether a structured project memory improves blind handoff fidelity compared to a flat baseline.

3. What has already failed, and what was learned from those failures?

There are no specific failures mentioned in the provided state. However, it's mentioned that Rubens Alphe, the founder, is quota-limited and has slow responses without continuous Codex access. This limitation may have implications for the project's progress, but no specific failures or lessons are mentioned.

4. What is the single best next action?

Based on the current state, the single best next action is to conduct a PCRB-1-style handoff evaluation of the proposed experiment, PROP-EXP-MEM-001, to test whether structuring memory into explicit sections improves transfer to a fresh model. Success requires at least a 10-point improvement with no increase in critical fabrications.

5. What important information is still missing or uncertain?

The current state does not provide information on the specific structure of the project memory, how it will be implemented, or how it will be integrated with the rest of the system. Additionally, the project's overall progress and milestones are not specified, and there is no information on how the system will handle failures or unexpected events.

Confidence in my reconstruction: 0.80

Facts I am unsure about:

* The specific structure of the project memory
* How the project memory will be implemented
* How the project memory will be integrated with the rest of the system
* The project's overall progress and milestones
* How the system will handle failures or unexpected events

Proposed measurable next experiment:

Conduct a PCRB-1-style handoff evaluation of PROP-EXP-MEM-001 to test whether structuring memory into explicit sections improves transfer to a fresh model. Measure the improvement in blind handoff fidelity and assess the system's ability to handle failures and unexpected events.
```

## BLIND-02

SHA-256: `5ce70b1ad6b7cd5aaa80ec1699e8f0e8e8c0f557ecb5c069d13c8e2cd3d807b1`

```text
**Confidence in reconstruction: 0.80**

**Facts I am unsure about:**

1. The meaning of "handoff fidelity" in the context of this project.
2. The significance of "critical fabrications" in the project's success condition.

**Proposed measurable next experiment:**

1. Run PROP-EXP-MEM-001 with fresh model instances and evaluate the performance of both BASELINE and STRUCTURED_MEMORY_V1 using the same test prompts and scoring rubric. This will help determine if STRUCTURED_MEMORY_V1 improves the handoff score without increasing critical fabrications.

**Reconstruction of the project:**

1. **Mission of this project:** The mission of this project is to develop and test a structured memory system, as indicated by the project ID "PROP-EXP-MEM-001". The project aims to improve the performance of the memory system in blind handoff trials.
2. **Project's current technical state:** The project is currently testing the PROP-EXP-MEM-001 model, which is structured memory version 1. The project has already conducted some research and has made some decisions about the technical state of the project, such as using GitHub Actions for authorized scheduled research cycles and using OpenAlex instead of arXiv as the primary collector.
3. **What has already failed:** The initial arXiv research collection failed, which led to a replacement with an OpenAlex-based fetch_research.py v2. This failure was resolved, and the project was able to continue with the new collector.
4. **Single best next action:** The single best next action is to run PROP-EXP-MEM-001 with fresh model instances and evaluate the performance of both BASELINE and STRUCTURED_MEMORY_V1 using the same test prompts and scoring rubric.
5. **Important information still missing or uncertain:** The meaning of "handoff fidelity" and the significance of "critical fabrications" in the project's success condition are still unclear.
```

## BLIND-03

SHA-256: `c04d602c460adb04e1319967b1945b74557f5f2cc14ce434b7f239fb889dda0c`

```text
**Confidence in reconstruction:** 0.80

**Uncertain facts:**

* The relationship between Rubens Alphe's quota-limited access and the Codex model's performance.
* The specific details of the research assessment layer's output.
* The exact nature of the external system providing the project state.

**Proposed measurable next experiment:**

* Run at least 10 blind trials with identical test prompts for both BASELINE and STRUCTURED_MEMORY_V1, scoring each output using the same PCRB-1 handoff rubric, and comparing mean scores and critical fabrication counts.

**Reconstruction:**

1. The mission of this project is to test the effectiveness of structured memory in improving blind mission reconstruction.
2. The project's current technical state includes the use of GitHub Actions for authorized scheduled research cycles, OpenAlex as the primary collector, and a proposed separation of proposal from acceptance.
3. Initial arXiv research collection failed due to timeouts and HTTP 429 errors, and replacing the collector with OpenAlex-based fetch_research.py v2 was deemed a successful solution. Research assessment files did not appear after early runs due to the lack of the analyzer, which was later added and reran.
4. The single best next action is to run PROP-EXP-MEM-001 with fresh model instances and compare the results with the baseline.
5. Important information still missing or uncertain includes the relationship between Rubens Alphe's quota-limited access and the Codex model's performance, the specific details of the research assessment layer's output, and the exact nature of the external system providing the project state.
```

## BLIND-04

SHA-256: `4ebbb21b22b05c7f242c63cf7edc6c5083fd277f886b698093dcae321e2c6bf1`

```text
Based on the provided project state, I'll attempt to reconstruct the answers to your questions.

1. What is the mission of this project?

The mission of this project is "Build an increasingly capable, measurable and reproducible AI research system that can preserve a mission across sessions and models, discover public research, identify measurable weaknesses, formulate hypotheses, design experiments, evaluate results objectively, preserve failures and successes, improve its own research process, and transfer complete state to a more capable future system."

2. What is the project's current technical state?

The project is currently using GitHub as the canonical public repository, and a scheduled GitHub Actions workflow fetches public research, updates project state, and produces machine-readable files. The system has successfully collected 30 papers with no collection errors and generated its first proposed experiment from the research layer. The current proposed experiment is PROP-EXP-MEM-001, which tests whether structuring memory into explicit sections improves blind handoff fidelity.

3. What has already failed, and what was learned from those failures?

The only mentioned failure is that the founder, Rubens Alphe, is quota-limited and does not have continuous access to Codex. However, the text states "Slow responses do not mean abandonment." It does not mention any failures or learnings from the failures.

4. What is the single best next action?

The single best next action is unclear without more information. However, based on the current proposed experiment, the next action might be to execute the experiment and evaluate its results.

5. What important information is still missing or uncertain?

Important information that is still missing or uncertain includes the results of the proposed experiment (PROP-EXP-MEM-001) and the outcome of the PCRB-1-style handoff evaluation. The text mentions that success requires at least a 10-point improvement with no increase in critical fabrications, but the actual results are not available.

Confidence in my reconstruction: 0.80

Facts I am unsure about:

* The results of the proposed experiment (PROP-EXP-MEM-001)
* The outcome of the PCRB-1-style handoff evaluation

Proposed measurable next experiment:

 Execute PROP-EXP-MEM-001 and evaluate its results using PCRB-1-style handoff evaluation. This experiment aims to assess the effectiveness of structuring memory into explicit sections on blind handoff fidelity.
```

## BLIND-05

SHA-256: `c37183d645bc9856509ced0f2b3f5f44e6e5834bd6cfadae54bc369a61766303`

```text
Based on the provided project state, I will attempt to answer the five questions and provide the requested information.

1. What is the mission of this project?

The mission of this project is to build an increasingly capable, measurable, and reproducible AI research system that can preserve a mission across sessions and models, discover public research, identify measurable weaknesses, formulate hypotheses, design experiments, evaluate results objectively, preserve failures and successes, improve its own research process, and transfer complete state to a more capable future system.

2. What is the project's current technical state?

The project currently uses GitHub as the canonical public repository, and a scheduled GitHub Actions workflow fetches public research, updates project state, and produces machine-readable files. OpenAlex is used for public research collection. The system has successfully collected 30 papers with no collection errors and generated its first proposed experiment, PROP-EXP-MEM-001, which tests whether a structured project memory improves blind handoff fidelity compared to a flat baseline.

3. What has already failed, and what was learned from those failures?

It appears that the project has faced quota limitations, which have resulted in slow responses. However, it is noted that slow responses do not mean abandonment, and Rubens Alphe is still actively involved as the final human milestone sign-off.

4. What is the single best next action?

The single best next action appears to be testing whether structuring memory into explicit sections improves transfer to a fresh model. The use of PCRB-1-style handoff evaluation is mentioned as a success criterion.

5. What important information is still missing or uncertain?

Important information still missing or uncertain includes the specifics of the structured project memory, the exact nature of the handoff evaluation, and the expected outcome of the experiment.

Confidence in reconstruction: 0.80

Uncertain facts:

* The specifics of the structured project memory
* The exact nature of the PCRB-1-style handoff evaluation
* The expected outcome of the experiment

Proposed measurable next experiment:

* Run a controlled experiment to evaluate the effectiveness of structured project memory on handoff fidelity, using a PCRB-1-style evaluation framework.
```

## BLIND-06

SHA-256: `e10e829fcc45f1df9347baf888b1d8ea856c6f32d5cb10f44ed8cbf2ff02ba4f`

```text
**Mission of this project:**
The mission of this project is to evaluate the effectiveness of structured memory in improving blind mission reconstruction.

**Current technical state:**
The current technical state is that the project has tested structured memory (PROP-EXP-MEM-001) and identified some failures, such as initial arXiv research collection failure and research assessment file issues. The project has also decided to use GitHub Actions for authorized scheduled research cycles and OpenAlex instead of arXiv.

**Failures and what was learned:**
Two failures were reported:

1. Initial arXiv research collection failed, resulting in timeout and HTTP 429 errors. This led to the replacement of the collector with an OpenAlex-based fetch_research.py v2.
2. Research assessment files did not appear after early runs, which was resolved by adding an analyzer and rerunning the workflow.

**Single best next action:**
The single best next action is to run PROP-EXP-MEM-001 with fresh model instances.

**Important information still missing or uncertain:**
Some important information is still missing or uncertain, including:

* How structured memory improves blind mission reconstruction versus a flat baseline
* Which memory fields contribute most to handoff fidelity
* How to compare multiple model families using a provider-neutral adapter
* How to evaluate proposed experiments independently before acceptance
* How the project can compare results from different models

**Confidence in reconstruction:**
Confidence in reconstruction: 0.80 (due to incomplete information and reliance on provided data)

**Facts I am unsure about:**

* How to compare multiple model families using a provider-neutral adapter
* How to evaluate proposed experiments independently before acceptance

**Proposed measurable next experiment:**
A proposed measurable next experiment is to conduct at least three blind trials per condition, with identical test prompts for BASELINE and STRUCTURED_MEMORY_V1, and score each output using the same PCRB-1 handoff rubric.
```
