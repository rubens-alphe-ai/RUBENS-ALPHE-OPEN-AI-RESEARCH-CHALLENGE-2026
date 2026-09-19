# Handoff benchmark

Document: `clinic.md` — 23 fact questions, 8 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| checklist | 96.4% | 91.0 to 101.7 | +31.2 pp (12.6 to 49.7) | 0 of 48 | 124 | 0 of 6 |
| sections | 84.1% | 75.1 to 93.0 | +18.8 pp (-0.9 to 38.6) | 0 of 48 | 126 | 0 of 6 |
| summary | 65.2% | 47.7 to 82.8 | control | 0 of 48 | 120 | 0 of 6 |
| facts_only | 61.6% | 53.2 to 70.0 | -3.6 pp (-17.0 to 9.7) | 0 of 48 | 150 | 5 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| checklist | 94.2% | 88.7 to 99.7 | +31.9 pp (17.0 to 46.8) | 0 of 48 | 122 | 0 of 6 |
| sections | 81.2% | 68.7 to 93.6 | +18.8 pp (2.3 to 35.3) | 0 of 48 | 122 | 0 of 6 |
| summary | 62.3% | 47.7 to 76.9 | control | 0 of 48 | 109 | 0 of 6 |
| facts_only | 57.2% | 50.5 to 64.0 | -5.1 pp (-17.1 to 7.0) | 0 of 48 | 149 | 0 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| checklist | 91.3% | 86.3 to 96.3 | +29.7 pp (8.6 to 50.8) | 0 of 48 | 117 | 0 of 6 |
| sections | 80.4% | 71.9 to 89.0 | +18.8 pp (1.4 to 36.3) | 0 of 48 | 122 | 0 of 6 |
| summary | 61.6% | 43.2 to 79.9 | control | 0 of 48 | 110 | 0 of 6 |
| facts_only | 57.2% | 50.5 to 64.0 | -4.3 pp (-19.3 to 10.6) | 0 of 48 | 149 | 0 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
