# Handoff benchmark

Document: `observatory.md` — 24 fact questions, 8 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| anchored | 71.5% | 62.2 to 80.9 | +0.7 pp (-11.2 to 12.6) | 0 of 48 | 115 | 0 of 6 |
| coverage | 71.5% | 67.2 to 75.8 | +0.7 pp (-3.6 to 5.0) | 0 of 48 | 115 | 0 of 6 |
| bare | 70.8% | 68.1 to 73.6 | control | 0 of 48 | 115 | 0 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| anchored | 76.4% | 68.7 to 84.0 | +11.1 pp (3.0 to 19.3) | 0 of 48 | 126 | 0 of 6 |
| coverage | 71.5% | 67.2 to 75.8 | +6.3 pp (0.2 to 12.3) | 0 of 48 | 119 | 0 of 6 |
| bare | 65.3% | 63.0 to 67.5 | control | 0 of 48 | 106 | 0 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| anchored | 76.4% | 69.2 to 83.5 | +11.8 pp (6.0 to 17.6) | 0 of 48 | 124 | 0 of 6 |
| coverage | 75.0% | 68.2 to 81.8 | +10.4 pp (2.2 to 18.6) | 0 of 48 | 122 | 0 of 6 |
| bare | 64.6% | 62.2 to 67.0 | control | 0 of 48 | 105 | 0 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
