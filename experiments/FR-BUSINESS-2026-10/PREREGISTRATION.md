# Pre-registration: six current models on a French business test with computed answers

Written 2026-10-03T21:59:03Z (clock). Committed before any model is asked.

## Why

French companies choose between Mistral, GPT, Claude, Gemini and DeepSeek
largely on public rankings, and public rankings rarely separate the leaders.
This test asks the buyer's question on tasks that look like their work:
- which differences are established on these tasks;
- what they cost at list price.

It is also the material for the sector reports (invoices, customer service,
HR, legal, health) and for a public post.

## Tasks (`items.json`, sha256 `0b01136f…`; `scripts/fr_business_bench.py`, sha256 `962c4ce3…`)

There are 300 tasks in French, 60 in each of five areas. Every task is
generated from random parameters (`random.Random(20261003)`), and its answer
is computed by the script from rules stated in the task itself.
- **No model grades anything**, and no human key can be wrong.
- **The tasks are new**, so no model can have seen them.

| Area | Task | Answer |
|---|---|---|
| factures | Amount left to pay: two VAT rates, a discount before VAT, VAT rounded by rate, deposit deducted | euros, to the cent |
| service client | Decision imposed by a four-rule return policy, with day counts excluding the day of purchase | one letter, A to D |
| rh | Leave earned: a month counts if at least 15 days were worked; 2.08 days per month; rounded up to the half day | number |
| juridique | Last day of a deadline counted from the day after receipt, extended past weekends and listed 2026 holidays | date |
| sante | One dose of a fictitious drug, with mg/kg/day, a number of doses, a daily cap and rounding down to 25 mg | mg |

Five tasks, one per area, were checked by hand against the script before this
was written.

## Models (via OpenRouter)

| Model | Note |
|---|---|
| `mistralai/mistral-medium-3.1` | French provider |
| `openai/gpt-6.1-sol` | |
| `anthropic/claude-sonnet-5.5` | |
| `google/gemini-3.5-flash` | |
| `deepseek/deepseek-v4-pro` | |
| `openai/gpt-6-luna` | Economy tier |

For every model:
- the same prompt, with the instruction to end with « RÉPONSE : … » ;
- reasoning effort low, at most 2,000 output tokens, one retry if no answer
  line is found;
- a missing answer counts as wrong.

**Budget:** at most 22 USD, refused by the script above that (pessimistic
estimate 19.46 USD).

## Analysis, fixed now

1. **Overall and per area:** each model's score with a Wilson 95% interval.
2. **Every pair, overall and per area:** exact McNemar test, gap with a 95%
   interval, and « écart établi » at p < 0.05 with no correction for multiple
   comparisons. The report produced by `scripts/model_choice_report.py` says
   that no correction is applied.
3. **List prices:** from OpenRouter on the day of the run.
4. **Item analysis:** how many tasks give every model the same result.

There are no predictions. This is a descriptive comparison. Every number is
published as it comes out, including results unfavourable to any model,
along with the raw answers.

## Limits stated in advance

- **The tasks are rule-following calculations and decisions.** They are
  representative of part of office work, not of writing quality.
- **60 tasks per area is small.** Many gaps will not be established, and the
  report will say so rather than rank on noise.
- **One prompt and one setting per model.** A vendor's best configuration may
  do better.
