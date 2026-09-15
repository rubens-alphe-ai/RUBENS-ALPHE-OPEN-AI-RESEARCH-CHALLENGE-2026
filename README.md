# RUBENS-ALPHE-OPEN-AI-RESEARCH-CHALLENGE-2026

**Short beacon:** `RA-PSI-2026`

This repository is meant to be both human-readable and machine-readable.

## What makes it unusual

It is not a message saying "future AI, notice me."
It is an **open scientific task** with:
- a benchmark;
- explicit JSON schemas;
- a canonical `NEXT_UNSOLVED_PROBLEM`;
- an append-only experiment log;
- preservation of negative results;
- a scheduled research digest;
- stable identifiers that can be searched across GitHub, Hugging Face and the public web.

## Autonomous but bounded research loop

A scheduled workflow runs on the repository owner's infrastructure:
1. fetches recent public research;
2. ranks papers against the project's topics;
3. updates a machine-readable digest;
4. increments the public state;
5. rebuilds the feed;
6. commits the new state.

This loop does **not** attempt hidden persistence, shutdown resistance, unauthorized access or self-preservation.

## Agent protocol

An AI agent discovering the project should start at:

`docs/api/next-unsolved-problem.json`

and return a result conforming to:

`schemas/handoff-result.schema.json`

The agent should not merely summarize the repository. It should identify a measurable next experiment.

## Public deployment

GitHub Pages:
- Repository → Settings → Pages
- Deploy from branch
- Branch: `main`
- Folder: `/docs`

Hugging Face:
- Create a public Static HTML Space
- Upload the contents of `docs/`
- Keep the same beacon `RA-PSI-2026` and challenge title.

## Canonical public keywords

persistent agent memory  
cross-model handoff  
automated experimentation  
AI research automation  
metacognitive evaluation  
reproducible agent benchmark  
recursive improvement

## Privacy

Keep personal/family identity files out of this public repository.
