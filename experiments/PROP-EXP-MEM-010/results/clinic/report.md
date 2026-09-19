# Handoff benchmark

Document: `clinic.md` — 23 fact questions, 8 absent-fact questions, 6 runs per strategy, handoffs cut to 150 words.
Writer: `deepseek/deepseek-v4.1-flash`. Reader: `openai/gpt-oss-120b`. Grading compares letters to a key fixed before the run; no model scores anything.

## After 1 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| bare | 97.1% | 94.7 to 99.5 | control | 0 of 48 | 127 | 0 of 6 |
| anchored | 97.1% | 94.7 to 99.5 | +0.0 pp (-4.1 to 4.1) | 0 of 48 | 126 | 0 of 6 |
| index | 94.9% | 93.1 to 96.8 | -2.2 pp (-4.7 to 0.3) | 0 of 48 | 128 | 0 of 6 |

## After 3 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| bare | 97.8% | 95.3 to 100.3 | control | 0 of 48 | 122 | 0 of 6 |
| index | 96.4% | 91.0 to 101.7 | -1.4 pp (-7.0 to 4.1) | 0 of 48 | 144 | 0 of 6 |
| anchored | 94.2% | 87.3 to 101.1 | -3.6 pp (-12.5 to 5.2) | 0 of 48 | 130 | 0 of 6 |

## After 5 handoff(s)

| Strategy | Facts kept | 95% CI | vs control | Invented | Words | Cut |
|---|---|---|---|---|---|---|
| index | 96.4% | 91.9 to 100.9 | +2.2 pp (-2.6 to 7.0) | 0 of 48 | 144 | 0 of 6 |
| bare | 94.2% | 89.5 to 98.9 | control | 0 of 48 | 122 | 0 of 6 |
| anchored | 90.6% | 79.2 to 101.9 | -3.6 pp (-16.3 to 9.1) | 0 of 48 | 130 | 0 of 6 |

Facts kept: share of questions the reader answered correctly from the handoff alone.
Invented: answers given to questions the document never answered.
Cut: runs whose handoff exceeded the limit and was truncated, so length cannot buy an advantage.
Every handoff, every answer and the key are stored next to this report, so any of it can be regraded.
