# Handoff benchmark

Document: `document.md` — 30 fact questions, 10 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| sections | 83.3% | 81.1 to 85.5 | +3.9 pp (-4.2 to 12.0) | 0 of 60 | 150 | 4 of 6 |
| checklist | 82.2% | 73.7 to 90.7 | +2.8 pp (-7.5 to 13.0) | 0 of 60 | 133 | 0 of 6 |
| summary | 79.4% | 72.7 to 86.2 | control | 0 of 60 | 123 | 0 of 6 |
| facts_only | 63.3% | 63.3 to 63.3 | -16.1 pp (-22.9 to -9.3) | 0 of 60 | 150 | 6 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| sections | 82.2% | 78.6 to 85.8 | +4.4 pp (-5.1 to 14.0) | 0 of 60 | 124 | 0 of 6 |
| checklist | 80.6% | 71.3 to 89.8 | +2.8 pp (-9.4 to 15.0) | 0 of 60 | 132 | 0 of 6 |
| summary | 77.8% | 70.6 to 85.0 | control | 0 of 60 | 120 | 0 of 6 |
| facts_only | 61.7% | 59.8 to 63.6 | -16.1 pp (-22.1 to -10.1) | 0 of 60 | 149 | 0 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| sections | 81.7% | 78.0 to 85.3 | +5.6 pp (-2.9 to 14.0) | 0 of 60 | 124 | 0 of 6 |
| checklist | 80.0% | 69.4 to 90.6 | +3.9 pp (-7.9 to 15.7) | 0 of 60 | 131 | 0 of 6 |
| summary | 76.1% | 70.1 to 82.1 | control | 0 of 60 | 117 | 0 of 6 |
| facts_only | 63.3% | 63.3 to 63.3 | -12.8 pp (-18.8 to -6.8) | 0 of 60 | 149 | 0 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
