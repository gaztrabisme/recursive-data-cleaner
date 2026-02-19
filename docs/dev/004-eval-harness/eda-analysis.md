# EDA: Why Models Fail and How to Improve the Pipeline

**Date**: 2026-02-19
**Prerequisite**: [eval-results-v1.md](eval-results-v1.md)

---

## 1. The Efficiency Equation

Every model gets the same budget: **5 chunks x 5 max_iterations = 25 LLM calls**. The differentiator is how many of those calls produce accepted functions.

| Model | LLM Calls | Functions | Calls/Function | Wasted Calls | Eval Score |
|-------|-----------|-----------|----------------|-------------|------------|
| Coder-30B-A3B | 22 | 8 | 2.75 | 14 | 86.8% |
| 30B-A3B | 25 | 9 | 2.78 | 16 | **92.1%** |
| 8B | 25 | 7 | 3.57 | 18 | 73.7% |
| 4B | 25 | 6 | 4.17 | 19 | 76.3% |
| Next-80B-A3B | 25 | 6 | 4.17 | 19 | 76.3% |
| 14B | 25 | 4 | 6.25 | 21 | 61.8% |
| Coder-Next | 25 | 4 | 6.25 | 21 | 56.6% |

**Finding**: Score correlates with calls/function (r = -0.89), not parameter count. Models that produce accepted functions efficiently cover more issue types.

The "wasted calls" column shows calls that either: (a) were fruitless (no code), (b) failed validation, or (c) were cleanup iterations after `clean` status. With 12 cleaning tasks in the instructions and only 25 calls available, models need ~2 calls/function to cover everything. Only the top 2 models approach that ratio.

---

## 2. Failure Root Cause Taxonomy

### Tier 1: Incomplete Functions (all models, 5 lost assertions)

These aren't coverage gaps — every model generates a function for the affected field. The function just doesn't handle all variants.

**HTML entity decoding (2 failures, records 1 and 6):**

Every model generates an HTML cleanup function. They all strip tags (`<b>`, `<br/>`, `<p>`) correctly. None decode standalone entities (`&amp;` → `&`).

Looking at the generated code, all models use regex-based tag stripping:
```python
re.sub(r'<[^>]+>', '', text)  # Strips tags
```
None call `html.unescape()` or decode `&amp;`, `&lt;`, `&gt;` outside of tag context.

**Why**: The instruction says "Strip HTML tags and decode HTML entities." Models interpret this as a single operation (strip tags). The entity decoding is a separate operation they never add because the tag stripping "solves" the HTML issue in their analysis.

**Weight "lbs." trailing period (1 failure, record 4):**

6/7 models' weight regex expects `lbs` without trailing period. Only Coder-Next handles it (ironically the lowest scorer) because its regex uses `"lbs" in rest` substring matching rather than exact word matching.

```python
# Typical (fails on "11.5 lbs."):
re.match(r'([\d.]+)\s*(kg|lbs|lb|g)', weight_str)

# Coder-Next (works):
if "lbs" in rest or "lb" in rest:
    value_kg = num * 0.453592
```

### Tier 2: Missing Functions (model-dependent, 0-18 lost assertions)

These are coverage gaps — no function generated for the issue type at all.

| Issue Type | Models Missing It | Assertions Lost Per Model | Root Cause |
|-----------|-------------------|---------------------------|------------|
| category_case | 6/7 (all except 30B-A3B) | 5 | Declared clean before reaching it |
| null_empty (notes) | 7/7 | 3 | Never generated, all models |
| whitespace (name) | 3/7 (4B, Next-80B, Coder-Next) | 6 | No whitespace function generated |
| tag_format | 3/7 (14B, 8B, Coder-Next) | 5 | No tag normalizer generated |
| status enum_typo | 2/7 (14B partial, 8B partial) | 2-6 | Weak/no status function |
| weight_unit | 1/7 (14B) | 7 | No weight function at all |
| phone_format | 1/7 (Coder-Next) | 7 | Function exists but broken |

**Null/empty notes is the most interesting**: the instructions explicitly say "Replace empty strings and whitespace-only values with null in notes field." Every model is told to do this. None do. This suggests it's a **priority** issue — models tackle high-signal issues (dates, phones, amounts) first and either declare `clean` or exhaust their iteration budget before reaching this "boring" low-signal task.

### Tier 3: Structural — The 3/8 Category Baseline

All 6 models that lack a category function score exactly 3/8 on category_case. These 3 are the "already clean" assertions (records 0, 4, 7 where the input is already Title Case). This confirms: without a category function, 5/8 category values remain uncleaned, and 3/8 pass because they were never dirty.

---

## 3. Pipeline Architecture Analysis

### 3.1 Adaptive Iteration Budget

**Mechanism** (`cleaner.py:676-686`):
- `fruitless_iterations` increments when LLM says `needs_more_work` but provides no code
- At `fruitless_iterations >= 2`, the chunk is skipped
- Counter resets to 0 when a function passes all validation gates
- Validation failures do NOT increment the counter (they get retried with error feedback)

**Assessment**: The 2-fruitless rule is actually **less aggressive than it appears**. It only triggers when the LLM has nothing left to generate — not when validation fails. The real budget constraint is `max_iterations=5` combined with validation retries consuming iteration slots.

**Scenario analysis**: If a model generates 2 functions (iterations 0-1 productive, 2-3 fruitless) → exits after iteration 3. This leaves 1 unused iteration. If the model had produced a function on iteration 2, it would have reset and gotten iterations 3-4 as well.

**Verdict**: The fruitless budget is fine. The bottleneck is `max_iterations=5` and validation failure rate.

### 3.2 Duplicate Field Coverage

**Mechanism** (`cleaner.py:558-570`):
- `self._fields_covered` tracks which fields have accepted functions
- Cumulative across ALL chunks (by design — v1.1.0 cross-chunk dedup)
- If a new function targets an already-covered field, it's rejected

**Assessment**: This is correct and prevents duplicate work. But it means: if chunk 1 generates a weak `normalize_dates()` that handles 80% of date formats, no later chunk can generate a better one. The first-mover advantage is permanent.

**Impact on eval**: Not directly visible in current results because the benchmark has consistent date formats across chunks. But for real-world data with long-tail format variants, this could be limiting.

### 3.3 No-Op Detection

**Mechanism** (`metrics.py:131-173`):
- Tests function against sample data from the current chunk
- If all records unchanged after applying function → reject as no-op
- Uses `extract_sample_data()` which returns up to 3 records

**Risk**: If sample records happen to already be clean for the targeted field, a valid function is rejected. Example: null-normalization function tested on 3 records that all have non-empty notes → appears to do nothing → rejected.

**Assessment**: Moderate risk for low-frequency issues (null/empty affects 3/100 records = 3%). With 3 samples from a chunk of 20 records, the probability of all 3 being non-null is `(17/20)^3 = 61.4%`. This means the no-op gate has a **~61% chance of rejecting a valid null-normalization function**.

This is likely why no model generates a null-normalizer: even if a model generates one, the no-op gate probably kills it.

### 3.4 The Prompt

The prompt template (`prompt.py:82-141`) is well-structured but **generic**. It doesn't include:
- Examples of common transformation patterns
- Hints about `html.unescape()` for entity decoding
- Guidance on priority ordering (which issues to tackle first)

The user's instructions (`benchmark_instructions.txt`) are excellent — specific, actionable, covering all 12 issue types. But the LLM prompt template wraps them in a generic format that doesn't reinforce the specifics.

---

## 4. Causal Model: Why Models Underperform

```
                    ┌─────────────────────┐
                    │ 12 cleaning tasks    │
                    │ in instructions      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ 25 LLM calls budget │
                    │ (5 chunks × 5 iter) │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼─────────┐ ┌───▼───────────┐ ┌──▼──────────────┐
    │ Validation retries │ │ Fruitless     │ │ Premature       │
    │ consume calls      │ │ iterations    │ │ "clean" signal  │
    └─────────┬─────────┘ └───┬───────────┘ └──┬──────────────┘
              │               │                │
              └───────┬───────┘                │
                      │                        │
           ┌──────────▼──────────┐   ┌────────▼────────────┐
           │ Fewer productive    │   │ Low-signal issues    │
           │ iterations          │   │ never reached        │
           └──────────┬──────────┘   └────────┬────────────┘
                      │                       │
                      └────────┬──────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Coverage gaps:       │
                    │ category, null/empty │
                    │ whitespace, tags     │
                    └─────────────────────┘
```

**And separately:**

```
    ┌──────────────────────┐
    │ Function quality gap │
    └──────────┬───────────┘
               │
    ┌──────────▼──────────────────────┐
    │ HTML: tag stripping works,      │
    │ entity decoding not attempted   │
    │                                 │
    │ Weight: regex misses "lbs."     │
    │ trailing period variant         │
    └─────────────────────────────────┘
```

---

## 5. Improvement Opportunities

Ranked by **Impact / Effort** (potential assertion gains vs. engineering complexity).

### Tier A: High Impact, Low Effort

**A1. Add `html.unescape()` hint to prompt template**
- Impact: +2 assertions for ALL models (records 1, 6)
- Effort: 1-line prompt change
- How: Add to RULES section: `"For HTML cleanup, use html.unescape() to decode entities like &amp; → &, not just tag stripping"`
- Risk: None
- Projected best-model score: 72/76 → **94.7%**

**A2. Increase no-op sample size for rare issues**
- Impact: Unblocks null/empty function generation (+3 assertions for all models)
- Effort: Change `max_samples=3` to `max_samples=10` in `extract_sample_data()` for no-op gate
- How: `metrics.py:check_function_effect()` — pass more samples
- Risk: Slightly slower validation (negligible)
- Projected best-model score: 75/76 → **98.7%** (combined with A1)

**A3. Weight regex hint in prompt**
- Impact: +1 assertion for 6/7 models (record 4, "lbs." variant)
- Effort: Add example to prompt: `"Handle unit variants including 'lbs.' with trailing period"`
- Risk: None

### Tier B: Medium Impact, Medium Effort

**B1. Increase max_iterations from 5 to 8**
- Impact: More iterations → more functions generated → better coverage of low-signal issues
- Effort: Parameter change + rerun benchmarks
- Risk: Longer pipeline time (but MoE models are fast enough)
- Estimated gain: 2-4 more functions for models currently at 4-6 functions
- Trade-off: 8 iterations × 5 chunks = 40 LLM calls. For 30B-A3B at 24s/call, adds ~6 minutes

**B2. Issue priority guidance in prompt**
- Impact: Helps models tackle issues in optimal order — high-coverage first, then long-tail
- Effort: Add priority section to prompt: "Address issues in this order: data types (dates, amounts) → formatting (phones, emails) → normalization (status, category, weight) → cleanup (HTML, whitespace, null)"
- Risk: Models might over-focus on first priorities and still skip tail

**B3. Two-pass architecture for low-signal issues**
- Impact: After main pass completes, run a second targeted pass for uncovered issue types
- Effort: ~50 lines of code — check `_fields_covered` against instruction keywords, re-prompt for uncovered ones
- Risk: Adds complexity; may generate low-quality functions for edge cases

### Tier C: Lower Impact, Higher Effort (v2.0 territory)

**C1. Multi-function generation per iteration**
- Impact: Cover 2-3 simple issues per call instead of 1
- Effort: Significant prompt/parsing changes
- Risk: Response quality degrades when asking for multiple functions

**C2. Adaptive chunk sizing based on issue density**
- Impact: Dense chunks get more iterations, sparse chunks get fewer
- Effort: Requires pre-scanning or dynamic reallocation
- Risk: Over-engineering for marginal gain

**C3. Function refinement pass**
- Impact: After initial generation, re-evaluate each function against assertions
- Effort: New pipeline phase; needs golden data at runtime (defeats purpose)
- Risk: Circular dependency with eval harness

---

## 6. Projected Impact Matrix

Applying Tier A improvements to the current 30B-A3B score:

| Improvement | Assertions Fixed | New Score | Delta |
|-------------|-----------------|-----------|-------|
| Baseline (current) | — | 70/76 (92.1%) | — |
| + A1 (entity hint) | +2 (html records 1,6) | 72/76 (94.7%) | +2.6% |
| + A2 (no-op samples) | +3 (null records 1,3,6) | 75/76 (98.7%) | +3.9% |
| + A3 (weight hint) | +1 (weight record 4) | 76/76 (100%) | +1.3% |
| **All Tier A** | **+6** | **76/76 (100%)** | **+7.9%** |

For the weakest model (Coder-Next, 43/76):

| Improvement | Projected Score | Notes |
|-------------|----------------|-------|
| Baseline | 43/76 (56.6%) | |
| + Tier A | ~49/76 (64.5%) | +6 from systemic fixes |
| + B1 (more iterations) | ~55-60/76 (72-79%) | More functions generated |

---

## 7. Experiment Design

To validate these improvements without re-running all 7 models:

**Quick validation (1 model, ~10 min):**
1. Apply A1 + A2 + A3 to prompt/metrics
2. Re-run 30B-A3B only (fastest good model)
3. Eval against golden assertions
4. If score ≥ 75/76 → Tier A validated

**Full validation (all models, ~2.5 hours):**
1. Apply all Tier A + B1
2. Re-run all 7 models with `run_all.sh`
3. Eval all, regenerate comparison table
4. Compare before/after per model

**What to measure:**
- Functions generated (should increase with B1)
- Issue type coverage (should include null_empty and category_case more often)
- Calls/function ratio (should improve with A1-A3 reducing validation failures)
- Wall clock time (should increase modestly with B1)

---

## 8. Summary

The pipeline's architecture is sound. The eval harness reveals that **most failures trace to three root causes**:

1. **Function quality gap** (entity decoding, weight regex) — fixable with prompt hints
2. **No-op gate false positives** (null normalization) — fixable with larger sample size
3. **Iteration budget vs. issue count** (12 tasks, ~6-9 functions generated) — partially fixable with more iterations

Tier A improvements are low-risk, require no architectural changes, and project to raise the best model from 92.1% to 100% on the CRM benchmark. They should be the first thing implemented.
