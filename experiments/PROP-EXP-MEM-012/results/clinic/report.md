# Handoff benchmark

Document: `clinic.md` — 23 fact questions, 8 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| coverage | 75.4% | 71.6 to 79.1 | +0.7 pp (-2.7 to 4.2) | 0 of 48 | 126 | 0 of 6 |
| bare | 74.6% | 72.8 to 76.5 | control | 0 of 48 | 124 | 0 of 6 |
| anchored | 73.9% | 73.9 to 73.9 | -0.7 pp (-2.6 to 1.1) | 0 of 48 | 131 | 0 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| coverage | 83.3% | 79.9 to 86.8 | +8.7 pp (4.6 to 12.8) | 0 of 48 | 133 | 0 of 6 |
| anchored | 79.7% | 77.4 to 82.1 | +5.1 pp (1.6 to 8.5) | 0 of 48 | 140 | 0 of 6 |
| bare | 74.6% | 72.8 to 76.5 | control | 0 of 48 | 114 | 0 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| anchored | 84.8% | 81.0 to 88.6 | +10.9 pp (6.1 to 15.7) | 0 of 48 | 136 | 0 of 6 |
| coverage | 81.2% | 74.9 to 87.4 | +7.2 pp (0.4 to 14.1) | 0 of 48 | 124 | 0 of 6 |
| bare | 73.9% | 71.0 to 76.8 | control | 0 of 48 | 111 | 0 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
