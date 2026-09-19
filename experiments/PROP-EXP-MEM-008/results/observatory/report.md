# Handoff benchmark

Document: `observatory.md` — 24 fact questions, 8 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| checklist | 91.7% | 86.9 to 96.5 | +14.6 pp (9.2 to 19.9) | 0 of 48 | 117 | 0 of 6 |
| sections | 86.8% | 85.0 to 88.6 | +9.7 pp (4.4 to 15.0) | 0 of 48 | 112 | 0 of 6 |
| facts_only | 79.2% | 79.2 to 79.2 | +2.1 pp (-2.5 to 6.7) | 0 of 48 | 150 | 6 of 6 |
| summary | 77.1% | 72.5 to 81.7 | control | 0 of 48 | 110 | 0 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| checklist | 91.7% | 86.1 to 97.2 | +20.8 pp (15.3 to 26.4) | 0 of 48 | 117 | 0 of 6 |
| sections | 85.4% | 81.8 to 89.1 | +14.6 pp (5.5 to 23.7) | 0 of 48 | 111 | 0 of 6 |
| facts_only | 77.8% | 74.2 to 81.3 | +6.9 pp (-2.5 to 16.4) | 0 of 48 | 148 | 0 of 6 |
| summary | 70.8% | 64.1 to 77.6 | control | 0 of 48 | 106 | 0 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| checklist | 92.4% | 87.2 to 97.5 | +22.2 pp (15.1 to 29.4) | 0 of 48 | 117 | 0 of 6 |
| sections | 84.7% | 81.2 to 88.3 | +14.6 pp (5.5 to 23.7) | 0 of 48 | 111 | 0 of 6 |
| facts_only | 77.8% | 74.2 to 81.3 | +7.6 pp (-2.5 to 17.8) | 0 of 48 | 148 | 0 of 6 |
| summary | 70.1% | 62.6 to 77.7 | control | 0 of 48 | 106 | 0 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
