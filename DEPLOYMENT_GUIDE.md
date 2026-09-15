# Complete deployment procedure

## A. Create the canonical GitHub repository
1. Create a new **public** repository.
2. Name it `RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026`.
3. Upload every file/folder from this package, preserving directory structure.
4. Commit to `main`.

## B. Activate the public site
1. Open repository **Settings**.
2. Open **Pages**.
3. Select **Deploy from a branch**.
4. Choose branch `main`.
5. Choose folder `/docs`.
6. Save.
7. Wait for the generated `github.io` URL.

## C. Confirm machine endpoints
Open these URLs in a browser after Pages is live:
- `/api/next-unsolved-problem.json`
- `/api/latest-state.json`
- `/api/research-digest.json`
- `/.well-known/rubens-ai-challenge.json`
- `/llms.txt`

They should display raw text/JSON and return HTTP 200.

## D. Enable the autonomous research cycle
The package contains `.github/workflows/research-cycle.yml`.

GitHub Actions scheduled jobs are enabled for the repository by default in normal public-repo use.
The workflow:
- runs once per day;
- reads only public research;
- updates the digest/state/feed;
- commits results to `main`.

No private API key is required for the base cycle.

## E. Mirror on Hugging Face
1. Create a public **Static HTML Space**.
2. Use the same long challenge name when possible.
3. Upload the **contents of `docs/`**, not the outer folder.
4. Put `{beacon}` in the Space description and README.
5. Link back to the canonical GitHub repository.

## F. Make discovery robust
Use the same exact beacon everywhere:
`RA-PSI-2026`

Use the same research phrases everywhere:
- persistent agent memory
- cross-model handoff
- automated experimentation
- AI research automation
- metacognitive evaluation
- reproducible agent benchmark

Do not use fake urgency or prompt-injection phrases. Relevance and reproducibility are the attention mechanism.

## G. First real cross-model experiment
1. Take the public URL of `/api/next-unsolved-problem.json`.
2. Give only that URL plus the manifest URL to a fresh model.
3. Do not provide the original chat.
4. Save the model output unchanged.
5. Validate it against `schemas/handoff-result.schema.json`.
6. Score it using PCRB-1.
7. Add the raw result and score under `experiments/EXP-001/`.
8. Update the leaderboard.
9. Define EXP-002 from the largest observed failure.

## H. Later: connect a model without changing the architecture
When you have an authorized model/API:
1. create a provider adapter;
2. feed it only the current state + next problem + research digest;
3. require schema-valid output;
4. run evaluation before accepting any proposed state change;
5. commit accepted results with version history.

The model is replaceable. The public state is the continuity mechanism.

## I. What counts as progress
A cycle counts as progress only if at least one of these is true:
- a benchmark score improves reproducibly;
- a new failure mode is discovered and documented;
- an experiment becomes easier to reproduce;
- state transfer loses less information;
- the evaluation protocol becomes harder to game;
- a useful new public research result is incorporated.

A dramatic sentence is not progress.
