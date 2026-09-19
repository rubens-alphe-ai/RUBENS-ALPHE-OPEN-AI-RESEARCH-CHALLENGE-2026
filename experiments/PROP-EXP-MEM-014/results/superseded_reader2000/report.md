# Handoff benchmark

Document: `document.md` — 30 fact questions, 10 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| checklist | 86.7% | 79.2 to 94.2 | +11.7 pp (-4.8 to 28.2) | 0 of 40 | 136 | 0 of 4 |
| sections | 81.7% | 67.6 to 95.7 | +6.7 pp (-12.2 to 25.5) | 0 of 40 | 145 | 1 of 4 |
| summary | 75.0% | 58.5 to 91.5 | control | 0 of 40 | 121 | 0 of 4 |
| facts_only | 62.8% | 61.3 to 64.2 | -12.5 pp (-28.9 to 3.9) | 0 of 60 | 150 | 6 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| checklist | 85.0% | 79.7 to 90.3 | +27.5 pp (-10.8 to 65.8) | 0 of 40 | 136 | 0 of 4 |
| sections | 79.2% | 65.2 to 93.1 | +21.7 pp (-20.0 to 63.3) | 0 of 40 | 133 | 0 of 4 |
| facts_only | 62.8% | 61.3 to 64.2 | +5.0 pp (-32.9 to 42.9) | 0 of 60 | 150 | 0 of 6 |
| summary | 57.5% | 20.9 to 94.1 | control | 0 of 40 | 111 | 0 of 4 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| checklist | 84.2% | 79.1 to 89.2 | +25.8 pp (-11.0 to 62.7) | 0 of 40 | 136 | 0 of 4 |
| sections | 79.2% | 65.2 to 93.1 | +20.8 pp (-17.0 to 58.7) | 0 of 40 | 133 | 0 of 4 |
| facts_only | 62.8% | 61.3 to 64.2 | +4.2 pp (-30.6 to 38.9) | 0 of 60 | 150 | 0 of 6 |
| summary | 58.3% | 24.7 to 92.0 | control | 0 of 40 | 111 | 0 of 4 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
Failed runs, excluded and listed in report.json: 6.
