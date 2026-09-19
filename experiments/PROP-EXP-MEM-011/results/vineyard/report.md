# Handoff benchmark

Document: `vineyard.md` — 24 fact questions, 8 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| anchored | 79.9% | 76.6 to 83.2 | +6.9 pp (-2.1 to 16.0) | 0 of 48 | 113 | 0 of 6 |
| index | 78.5% | 74.2 to 82.8 | +5.6 pp (-3.5 to 14.6) | 0 of 48 | 108 | 0 of 6 |
| bare | 72.9% | 65.2 to 80.6 | control | 0 of 48 | 103 | 0 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| index | 78.5% | 75.2 to 81.8 | +6.2 pp (-2.8 to 15.3) | 0 of 48 | 118 | 0 of 6 |
| anchored | 77.1% | 73.4 to 80.7 | +4.9 pp (-6.0 to 15.7) | 0 of 48 | 120 | 0 of 6 |
| bare | 72.2% | 63.6 to 80.8 | control | 0 of 48 | 96 | 0 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| index | 79.2% | 76.4 to 81.9 | +5.6 pp (-0.4 to 11.5) | 0 of 48 | 109 | 0 of 6 |
| anchored | 79.2% | 76.4 to 81.9 | +5.6 pp (-2.6 to 13.7) | 0 of 48 | 119 | 0 of 6 |
| bare | 73.6% | 67.6 to 79.6 | control | 0 of 48 | 96 | 0 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
