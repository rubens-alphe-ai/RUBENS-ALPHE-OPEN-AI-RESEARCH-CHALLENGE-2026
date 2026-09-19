# Handoff benchmark

Document: `observatory.md` — 24 fact questions, 8 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| bare | 79.2% | 73.6 to 84.7 | control | 0 of 48 | 114 | 0 of 6 |
| index | 72.9% | 69.3 to 76.6 | -6.2 pp (-10.8 to -1.7) | 0 of 48 | 115 | 0 of 6 |
| anchored | 70.8% | 66.0 to 75.6 | -8.3 pp (-15.7 to -1.0) | 0 of 48 | 114 | 0 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| anchored | 75.7% | 68.2 to 83.2 | +4.9 pp (-5.3 to 15.0) | 0 of 48 | 117 | 0 of 6 |
| bare | 70.8% | 66.0 to 75.6 | control | 0 of 48 | 109 | 0 of 6 |
| index | 70.1% | 64.3 to 76.0 | -0.7 pp (-7.7 to 6.3) | 0 of 48 | 116 | 0 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| anchored | 73.6% | 66.0 to 81.3 | +3.5 pp (-9.6 to 16.6) | 0 of 48 | 121 | 0 of 6 |
| bare | 70.1% | 64.3 to 76.0 | control | 0 of 48 | 108 | 0 of 6 |
| index | 68.1% | 62.8 to 73.4 | -2.1 pp (-10.7 to 6.6) | 0 of 48 | 109 | 0 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
