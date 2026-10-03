# Release-day check: gpt-6.1-sol on Epoch AI's public data

**Source.** Epoch AI benchmark data (CC BY 4.0), downloaded 2026-10-03; the
same bundle as `experiments/LEADERBOARD-REALITY-2026-10/`.

**Model.** `gpt-6.1-sol` (OpenAI), release date 2026-09-29 in that data. It is
the most recently released model in the bundle.

**Rule.**
- 95%, unpaired, using Epoch's published standard errors.
- Each model counts once, at its best setting.
- No correction for multiple comparisons.
- Only benchmarks with at least five other models are used.

Reproduce with:

```
python scripts/launch_check.py --zip experiments/LEADERBOARD-REALITY-2026-10/epoch_benchmark_data_2026-10-03.zip --model gpt-6.1-sol
```

## Result

Nine benchmarks qualify.

| Benchmark | Score | Rank | Best other model | Gap (pts), 95% interval | Reading |
|---|---|---|---|---|---|
| FrontierMath Tier 4 v2 | 100.0 | 1 / 64 | gpt-6-astra_high 97.6 | +2.4 [−2.3, +7.1] | first, lead not established |
| FrontierMath Tiers 1–3 v2 | 93.7 | 1 / 81 | gpt-6-astra_max 93.7 | 0.0 [−4.0, +4.0] | level |
| OTIS Mock AIME 2024–2025 | 100.0 | 1 / 197 | claude-sonnet-5-5_max 100.0 | 0.0 | level (11 models at 100%; 37 other models not separated from it) |
| SimpleQA Verified | 73.9 | 2 / 77 | gpt-6-astra_max 75.6 | −1.7 [−5.5, +2.1] | behind, not separated |
| Furniture assembly | 80.0 | 2 / 29 | claude-opus-5-5_max 83.3 | −3.3 [−16.7, +10.0] | behind, not separated |
| Mystery game puzzles | 80.0 | 2 / 73 | gpt-6-astra_max 84.0 | −4.0 [−14.7, +6.7] | behind, not separated |
| GPQA Diamond | 95.4 | 3 / 219 | gpt-6-astra_max 95.8 | −0.4 [−4.2, +3.4] | behind, not separated (31 models tied with it) |
| Chess puzzles | 61.0 | 4 / 141 | gpt-6-astra_max 72.0 | −11.0 [−24.1, +2.1] | behind, not separated |
| EBR-Bench | 54.3 | 4 / 11 | gpt-6-astra_max 76.2 | −21.9 [−41.8, −2.0] | **behind, gap established** |

**Reading.**
- The model is first alone on one benchmark, and that lead is inside the error
  bars.
- It is level with the best other model on two benchmarks.
- It is behind on six. On five of these the gap is not separated; on one it
  is.

On this data it is a model in the top group, not a model shown to be on top.
"Not established" means not shown at this sample size; it does not mean false.

## Limits

- **The comparison is unpaired.** A paired test on per-item results would
  separate some pairs that this one cannot.
- **It uses Epoch's runs, not the vendor's.** Scores announced by the vendor
  may come from other settings.
- **It is one snapshot**, taken four days after release.
