# Handoff benchmark

Document: `vineyard.md` — 24 fact questions, 8 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| index | 97.2% | 95.0 to 99.5 | +1.4 pp (-0.9 to 3.6) | 0 of 48 | 139 | 2 of 6 |
| anchored | 96.5% | 94.7 to 98.3 | +0.7 pp (-1.1 to 2.5) | 0 of 48 | 130 | 0 of 6 |
| bare | 95.8% | 95.8 to 95.8 | control | 0 of 48 | 132 | 0 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| index | 97.2% | 95.0 to 99.5 | +2.1 pp (-0.3 to 4.5) | 0 of 48 | 136 | 0 of 6 |
| bare | 95.1% | 93.4 to 96.9 | control | 0 of 48 | 129 | 0 of 6 |
| anchored | 95.1% | 93.4 to 96.9 | +0.0 pp (-2.8 to 2.8) | 0 of 48 | 148 | 2 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| index | 96.5% | 93.2 to 99.8 | +0.7 pp (-2.6 to 4.0) | 0 of 48 | 133 | 0 of 6 |
| bare | 95.8% | 95.8 to 95.8 | control | 0 of 48 | 128 | 0 of 6 |
| anchored | 94.4% | 92.2 to 96.7 | -1.4 pp (-3.6 to 0.9) | 0 of 48 | 149 | 2 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
