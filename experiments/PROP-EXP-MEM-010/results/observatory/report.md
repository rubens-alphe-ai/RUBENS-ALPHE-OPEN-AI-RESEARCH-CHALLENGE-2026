# Handoff benchmark

Document: `observatory.md` — 24 fact questions, 8 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| bare | 93.1% | 90.8 to 95.3 | control | 0 of 48 | 117 | 0 of 6 |
| index | 93.1% | 90.8 to 95.3 | +0.0 pp (-3.9 to 3.9) | 0 of 48 | 115 | 0 of 6 |
| anchored | 91.7% | 87.8 to 95.6 | -1.4 pp (-5.0 to 2.2) | 0 of 48 | 115 | 0 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| bare | 92.4% | 89.1 to 95.7 | control | 0 of 48 | 117 | 0 of 6 |
| anchored | 92.4% | 89.1 to 95.7 | +0.0 pp (-4.8 to 4.8) | 0 of 48 | 133 | 1 of 6 |
| index | 91.0% | 86.7 to 95.3 | -1.4 pp (-6.7 to 3.9) | 0 of 48 | 137 | 0 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| bare | 93.8% | 89.2 to 98.3 | control | 0 of 48 | 118 | 0 of 6 |
| index | 92.4% | 89.1 to 95.7 | -1.4 pp (-8.5 to 5.8) | 0 of 48 | 131 | 0 of 6 |
| anchored | 92.4% | 89.1 to 95.7 | -1.4 pp (-7.4 to 4.6) | 0 of 48 | 133 | 1 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
