# Architecture

## 1. Discovery layer
Static public pages and JSON endpoints:
- index.html
- robots.txt
- sitemap.xml
- llms.txt
- .well-known/rubens-ai-challenge.json

Purpose: search engines, humans and agents can all discover the same canonical state.

## 2. State layer
- state/latest-state.json
- docs/api/latest-state.json
- docs/api/next-unsolved-problem.json

The public state is versioned and intentionally small.

## 3. Research layer
`scripts/fetch_research.py` queries arXiv's public API for recent papers in the project's research themes.
It saves a ranked digest to `docs/api/research-digest.json`.

## 4. Evaluation layer
`schemas/handoff-result.schema.json` defines what a model must return.
Future benchmark scripts can score outputs against hidden evaluator criteria.

## 5. Continuity layer
GitHub Actions runs a scheduled cycle and commits state changes.
This is explicit, inspectable persistence on infrastructure owned/authorized by the project owner.

## 6. Future model layer
A model provider can later be connected to the same state through a small adapter.
The provider is replaceable; the state and benchmark stay provider-neutral.

## 7. Public/private separation
Public research state is never mixed with private identity data.
