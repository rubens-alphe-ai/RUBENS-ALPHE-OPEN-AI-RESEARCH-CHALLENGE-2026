# Handoff benchmark

Document: `clinic.md` — 23 fact questions, 8 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| bare | 75.4% | 73.0 to 77.7 | control | 0 of 48 | 127 | 0 of 6 |
| anchored | 73.2% | 69.8 to 76.6 | -2.2 pp (-7.8 to 3.4) | 0 of 48 | 124 | 0 of 6 |
| index | 71.7% | 67.9 to 75.6 | -3.6 pp (-8.1 to 0.9) | 0 of 48 | 127 | 0 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| bare | 76.1% | 73.6 to 78.6 | control | 0 of 48 | 118 | 0 of 6 |
| anchored | 76.1% | 70.5 to 81.7 | +0.0 pp (-6.5 to 6.5) | 0 of 48 | 136 | 0 of 6 |
| index | 68.8% | 61.5 to 76.2 | -7.2 pp (-13.5 to -1.0) | 0 of 48 | 117 | 0 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| anchored | 77.5% | 67.0 to 88.1 | +3.6 pp (-8.8 to 16.0) | 0 of 48 | 122 | 0 of 6 |
| bare | 73.9% | 68.9 to 78.9 | control | 0 of 48 | 114 | 0 of 6 |
| index | 71.0% | 64.1 to 77.9 | -2.9 pp (-7.6 to 1.8) | 0 of 48 | 114 | 0 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
