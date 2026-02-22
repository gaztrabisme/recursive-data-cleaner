# Phase 2 RL Design: Reward Functions for Data Cleaning

**Date**: 2026-02-22
**Mode**: Design (discussion)
**Status**: Early exploration — no implementation decisions made

---

## 1. What We're Training

The model generates a structured XML response containing:
- Issue identification (which problems exist, which are already solved)
- One Python function (name, docstring, code)
- Self-written test cases (3-5 assertions)
- Chunk status judgment (clean / needs_more_work)

The RL action is the full text output. The design question is: what's the reward?

## 2. Current Quality Signals (and the gap)

The pipeline has 6 sequential validation gates, all binary pass/fail:

| Gate | Signal | RL Value |
|------|--------|----------|
| XML/Python parse | Binary | Floor constraint, not discriminative |
| Safety check | Binary | Rarely fires |
| Duplicate field | Soft warn | Weak signal |
| Runtime execution | Binary | Strong — "does the code run?" |
| Self-written tests | Binary per assertion | **High** — model writes its own ground truth |
| No-op detection | Binary | Strong — "did anything change?" |

**The gap**: No continuous reward exists per-function. The eval harness gives a continuous score (e.g., 73/76 = 96.1%), but it measures the whole pipeline output, not individual functions. And `compare_quality()` computes null/empty reduction percentages but only uses them for reporting.

## 3. Three Natural Reward Surfaces

### 3.1 Golden Assertion Correctness (primary)

We already have `(record_index, field, expected_value, match_mode)` tuples. Currently they evaluate the full chain. But you can filter assertions to the function's target field:

```
R_correctness = (assertions satisfied for this field) / (total assertions for this field)
```

`normalize_phone_numbers` gets scored against the 8 phone_format assertions. `fix_category_case` gets scored against the 8 category_case assertions. Per-function, continuous, 0.0 to 1.0.

### 3.2 Self-Consistency (calibration signal)

The model already emits `<test_cases>`. We can score:
- What fraction of its own tests pass?
- Do its self-tests agree with golden assertions? (penalize when self-tests pass but golden fails — deceptive self-assessment)

```
R_calibration = agreement(self_tests, golden_assertions)
```

This trains the model to write honest test cases, not just ones that trivially pass.

### 3.3 Effect Magnitude (anti-no-op, graded)

`check_function_effect` currently returns binary. Extend to:

```
R_effect = (records actually modified) / (records that needed modification)
```

A phone normalizer that fixes 7/8 phones scores 0.875. One that's a no-op scores 0.0.

## 4. The Corruption Pipeline (Training Data Source)

Instead of relying on manually-curated golden assertions (which don't scale), generate training data:

1. **Start with clean data** (or data already cleaned and verified)
2. **Systematically corrupt it** — introduce known issues per field:
   - Phone: strip country code, add parens, add dashes
   - Date: swap to MM/DD/YYYY, use Unix timestamps, spell out months
   - Status: introduce typos (`actve`, `acitve`, `pendng`)
   - Case: randomize capitalization
3. **The reward is reconstruction fidelity**: how close to the original clean value did the function get?

```
R_reconstruction = exact_match(cleaned_value, original_clean_value)
```

Why this is elegant:
- Ground truth is free (it's the pre-corruption data)
- Difficulty is controllable (corruption density, number of issue types per record)
- Issue types map directly to existing taxonomy (11 types)
- No human labeling after building the corruptor
- Unlimited training data generation
- Does double duty: generates RL training data AND builds DataCleanBench

## 5. Key Design Decisions

### Per-Function vs Per-Pipeline Reward

Per-function is more tractable — shorter horizon, clearer attribution, more training signal per dataset. But it misses composition effects (function A breaking function B's input).

A hybrid might work: per-function reward for individual quality + a small pipeline-level bonus for composition success.

### GRPO Structure

GRPO (Group Relative Policy Optimization) needs multiple completions per prompt to compute advantages. The pipeline naturally supports this — same data chunk, same context, generate N candidate functions, reward each, update toward the better ones.

The prompt is already deterministic (data + schema + context + instructions). The stochasticity is in the model's generation. So:

1. Present the same chunk+context prompt
2. Generate K completions (K=4-8)
3. Score each with the composite reward
4. GRPO update: push probability mass toward higher-reward completions

### Composite Reward Function

```
R = w1 * R_correctness     # Did it produce the right values?
  + w2 * R_format          # Did XML/Python parse? (binary)
  + w3 * R_effect          # Did it actually change data?
  + w4 * R_calibration     # Are self-tests honest?
  - w5 * R_safety_penalty  # Dangerous code penalty
```

The weights need tuning, but correctness should dominate.

## 6. What's Hard

1. **Attribution**: If `normalize_dates` produces wrong output, is it the function's fault, or did `fix_whitespace` (run earlier) mangle the date field? Per-function eval in isolation avoids this, but then you miss composition bugs.

2. **Stochastic variance**: 30B-A3B scores 7/8 or 8/8 on phone_format depending on the run. RL needs stable reward signal. Multiple eval runs per reward computation? Expensive with local models.

3. **Constrained decoding**: The model must produce valid XML with valid Python inside it. Unconstrained RL will explore outputs that fail at Gate 1 (parse). Constrained decoding (forcing valid XML structure) would focus exploration on code quality rather than wasting samples on format errors.

4. **The ceiling problem**: 30B-A3B is already at 96.1%. The remaining 3.9% is 2 HTML entity failures (hard floor — needs `html.unescape()` which models don't reliably generate) and 1 stochastic phone. RL can't push past a capability ceiling. It needs headroom to be worth the training cost.

## 7. Proposed Path of Least Resistance

1. **Build the corruption pipeline first** — it's the training data factory, useful even without RL (for eval dataset generation, DataCleanBench)
2. **Start with per-function GRPO** using `R_correctness` from golden assertions as the primary reward — simplest setup, clearest signal
3. **Add constrained decoding** to avoid wasting samples on format failures
4. **Defer composition-level RL** until per-function quality is saturated

## 8. Existing Infrastructure We'd Reuse

| Component | Location | Role in RL |
|-----------|----------|------------|
| `compute_field_stats()` | `stats.py` | Training data metadata |
| `format_stats_for_prompt()` | `stats.py` | Prompt construction |
| `build_prompt()` | `prompt.py` | Generate training prompts |
| `parse_response()` | `response.py` | Parse model output for reward eval |
| `validate_function()` | `validation.py` | Runtime gate (R_format component) |
| `validate_test_cases()` | `validation.py` | Self-consistency (R_calibration) |
| `check_function_effect()` | `metrics.py` | Effect magnitude (R_effect) |
| `check_code_safety()` | `validation.py` | Safety penalty |
| Golden assertions | `benchmarks/eval/golden/` | Primary correctness signal |
| `run_eval.py` | `benchmarks/eval/` | End-to-end scoring |
| `load_cleaning_module()` | `apply.py` | Execute generated functions |
