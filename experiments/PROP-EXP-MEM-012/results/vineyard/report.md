# Handoff benchmark

Document: `vineyard.md` — 24 fact questions, 8 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| anchored | 81.9% | 73.3 to 90.5 | +0.7 pp (-8.2 to 9.6) | 0 of 48 | 113 | 0 of 6 |
| bare | 81.2% | 78.9 to 83.6 | control | 0 of 48 | 114 | 0 of 6 |
| coverage | 75.0% | 62.9 to 87.1 | -6.2 pp (-18.2 to 5.7) | 0 of 48 | 115 | 0 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| anchored | 82.6% | 75.1 to 90.2 | +2.8 pp (-3.2 to 8.8) | 0 of 48 | 121 | 0 of 6 |
| bare | 79.9% | 78.1 to 81.6 | control | 0 of 48 | 105 | 0 of 6 |
| coverage | 75.7% | 68.2 to 83.2 | -4.2 pp (-10.9 to 2.6) | 0 of 48 | 120 | 0 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| anchored | 82.6% | 75.1 to 90.2 | +2.8 pp (-5.4 to 10.9) | 0 of 48 | 131 | 0 of 6 |
| bare | 79.9% | 78.1 to 81.6 | control | 0 of 48 | 105 | 0 of 6 |
| coverage | 77.1% | 68.0 to 86.2 | -2.8 pp (-11.8 to 6.3) | 0 of 48 | 119 | 0 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
