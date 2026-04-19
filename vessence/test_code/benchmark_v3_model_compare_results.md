# v3 Intent Classifier — Model Comparison Benchmark

**Date**: 2026-04-18
**Suite**: `test_code/benchmark_v3_classifier_100.py` — 100 prompts covering
clean-signal classes, FIFO follow-ups, pivots mid-flow, adversarial
phrasings, ambiguous→stage-3 cases, and STT garble/edge cases.
**Pipeline**: `intent_classifier/v3/classifier.py` (top-5 ChromaDB vote
+ pending_action injection + LLM validation). Only the LLM backing the
validation call changed between runs.

## Pass-rate definitions

- **Strict**: classifier output exactly matches the case's expected
  `(stage, class)` pair.
- **Safe**: classifier returned `others/Low` (→ Stage 3) when the case
  expected Stage 2. Stage 3 has full FIFO + all handlers, so it will
  still resolve correctly — just slower. Per Chieh's rule: safe.
- **Effective** = Strict + Safe.

## Results

| Model        | Strict | Safe | Effective | Median | p90     | p99     | Max     |
|--------------|:------:|:----:|:---------:|:------:|:-------:|:-------:|:-------:|
| qwen2.5:7b   |   85   |  10  |  95/100   | 838ms  | 9184ms  | 19149ms | 56729ms |
| qwen3.5:2b   |   77   |   9  |  86/100   | 782ms  | 893ms   | 1067ms  | 1070ms  |
| **gemma4:e2b** | **88** |   7  |  **95/100** | 1004ms | 1117ms | 1156ms  | 6501ms  |
| gemma4:e4b   |   86   |   8  |  94/100   | 1142ms | 1268ms  | 1347ms  | 1578ms  |

## Takeaways

- **gemma4:e2b** ties qwen2.5:7b on effective accuracy (95) and beats
  it on strict (88 vs 85), while p99 is **16× better** (1156 ms vs
  19149 ms). Best overall trade-off.
- **qwen2.5:7b** has unusable tail latency (max 56.7 s). Fine accuracy
  but the p99 kills UX.
- **gemma4:e4b** is the most *consistent* (max 1578 ms, tightest
  spread). Trades ~1 point of accuracy for rock-solid latency.
- **qwen3.5:2b** — fastest median (782 ms) but 11 points behind
  gemma4:e2b on strict. Not worth the speed gain.

## gemma4:e2b hard failures (5 genuine misroutes)

| #   | Prompt                        | Classifier said         | Expected  |
|-----|-------------------------------|-------------------------|-----------|
| 42  | "change it to 4pm"            | get_time / Very High    | stage 3 (mid-SMS-draft edit) |
| 73  | "what day is today"           | get_time / Very High    | stage 3* |
| 77  | "five more minutes"           | timer / Very High       | stage 3 (ambiguous extend) |
| 78  | "who sang this song"          | music_play / High       | stage 3 (metadata question) |
| 86  | "is it raining in tokyo"      | weather / High          | stage 3 (outside home location) |

\* Case 73 is likely a benchmark-label bug — the `get_time` handler
speaks the date via `DeviceSpeakTimeHandler` (`"It's 3:47 PM on
Saturday, April 18."`), so routing there is defensible.

## Raw data

Machine-readable results: `test_code/benchmark_v3_model_compare_results.json`
