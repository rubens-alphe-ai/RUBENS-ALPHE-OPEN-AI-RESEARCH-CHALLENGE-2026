# Handoff benchmark

Document: `vineyard.md` — 24 fact questions, 8 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| facts_only | 97.5% | 92.9 to 102.1 | +16.7 pp (10.3 to 23.0) | 0 of 40 | 150 | 5 of 5 |
| checklist | 97.2% | 93.7 to 100.8 | +16.0 pp (12.7 to 19.3) | 0 of 48 | 150 | 3 of 6 |
| sections | 91.7% | 91.7 to 91.7 | +10.4 pp (8.0 to 12.8) | 0 of 48 | 150 | 4 of 6 |
| summary | 81.2% | 78.9 to 83.6 | control | 0 of 48 | 107 | 0 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| facts_only | 97.5% | 92.9 to 102.1 | +17.5 pp (9.8 to 25.2) | 0 of 40 | 150 | 2 of 5 |
| checklist | 96.5% | 93.2 to 99.8 | +16.7 pp (12.8 to 20.6) | 0 of 48 | 127 | 0 of 6 |
| sections | 88.9% | 86.6 to 91.1 | +9.0 pp (3.9 to 14.1) | 0 of 48 | 138 | 0 of 6 |
| summary | 79.9% | 76.6 to 83.2 | control | 0 of 48 | 104 | 0 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| facts_only | 97.5% | 92.9 to 102.1 | +18.3 pp (9.7 to 27.0) | 0 of 40 | 148 | 0 of 5 |
| checklist | 96.5% | 93.2 to 99.8 | +16.7 pp (12.8 to 20.6) | 0 of 48 | 127 | 0 of 6 |
| sections | 88.9% | 86.6 to 91.1 | +9.0 pp (2.6 to 15.5) | 0 of 48 | 138 | 0 of 6 |
| summary | 79.9% | 75.6 to 84.2 | control | 0 of 48 | 104 | 0 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
Failed runs, excluded and listed in report.json: 1.
