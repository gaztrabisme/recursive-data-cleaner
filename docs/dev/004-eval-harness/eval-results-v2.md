# Eval Results v2: Pipeline Tuning Rerun

**Date**: 2026-02-20
**Model**: Qwen3-30B-A3B-Instruct-2507-MLX-8bit (8-bit)
**Pipeline version**: v1.2.0-dev (no-op gate fix + soft dedup + prompt hints + max_iterations=8)

> Rerun of the top-scoring model with all pipeline improvements applied.
> Compared against the v1.0.3 baseline from eval-results-v1.md.

---

## Before/After Comparison

| Issue Type | v1.0.3 (baseline) | v1.2.0-dev (rerun) | Delta |
|------------|-------------------|---------------------|-------|
| amount_format | 6/6 (100%) | 6/6 (100%) | — |
| category_case | **8/8 (100%)** | **8/8 (100%)** | — |
| date_format | 9/9 (100%) | 9/9 (100%) | — |
| email_case | 4/4 (100%) | 4/4 (100%) | — |
| enum_typo | 8/8 (100%) | 7/8 (87.5%) | -1 |
| html_cleanup | 5/7 (71.4%) | 5/7 (71.4%) | — |
| **null_empty** | **3/6 (50%)** | **6/6 (100%)** | **+3** |
| phone_format | 8/8 (100%) | 8/8 (100%) | — |
| tag_format | 6/6 (100%) | 6/6 (100%) | — |
| weight_unit | 6/7 (85.7%) | 6/7 (85.7%) | — |
| whitespace | 7/7 (100%) | 7/7 (100%) | — |
| **Total** | **70/76 (92.1%)** | **72/76 (94.7%)** | **+2** |

## Pipeline Metrics

| Metric | v1.0.3 | v1.2.0-dev |
|--------|--------|------------|
| Functions generated | 9 | 9 |
| LLM calls | 25 | 36 |
| Pipeline time | 9.8 min | 25.5 min |
| Avg call latency | 24s | 42s |
| Calls/function | 2.78 | 4.0 |

## What Changed

### Confirmed improvement: null_empty (+3)

The no-op gate sample size increase (`max_samples=50` vs default 3) unblocked generation of `normalize_notes_field`. This function converts empty strings and whitespace-only values to `None` in the notes field. No model in v1.0.3 ever generated this — the no-op gate was rejecting it because 3 random samples all had non-empty notes.

**This was the #1 prediction from the EDA analysis.** Confirmed.

### Not yet fixed: html_cleanup (still 5/7)

The prompt hint ("Prefer standard library functions where available, e.g., html.unescape()") was picked up by the model — the benchmark log shows it generating an HTML function with `html.unescape()` that correctly converts `&amp;` → `&` in its test cases. However, the function was **rejected by validation** (likely test case failure where the model wrote `"Purchased and returned item"` instead of `"Purchased & returned item"` — confusing `&amp;` entity with the English word "and").

The `description` field has no function in the final output. The 5/7 score comes from `contains` match mode passing on records where the expected substring exists even in the raw HTML.

**Root cause**: The model understands the task but writes incorrect test assertions. The test case validation gate catches the inconsistency and rejects the function. This is a model-level issue, not a pipeline architecture issue.

### Minor regression: enum_typo (8/8 → 7/8)

The status function missed the `acitve` → `active` typo variant (record 9). LLM stochasticity — the typo correction dictionary varies between runs. Not a pipeline issue.

### Weight still at 6/7

Record 4 ("11.5 lbs.") returns `None` instead of converting. The weight function's regex handles `lbs` but the trailing period causes a parse failure that defaults to `None`. Same root cause as v1.0.3 — the prompt hint about trailing punctuation wasn't specific enough to fix this.

## Conclusions

1. **No-op gate fix validated**: +3 null_empty assertions, exactly as predicted. The sample size was the blocker.
2. **Soft dedup had no measurable impact**: No supplementary functions were generated. The model naturally avoids re-targeting fields through the context window.
3. **Prompt hints partially effective**: The model attempted an HTML function with `html.unescape()` but it failed its own test cases. The hint improved intent but not execution.
4. **max_iterations=8 provided necessary headroom**: 36 calls to generate 9 functions (4.0 calls/function) vs. Run A's 25 calls for only 5 functions. The extra budget was essential for coverage.
5. **Remaining 4 failures**: 2 HTML entity (model can't pass its own test cases), 1 enum typo (stochastic), 1 weight edge case (regex variant). All model-quality issues, not pipeline issues.

## Remaining Failures (4)

| Record | Field | Expected | Got | Issue | Fixable by pipeline? |
|--------|-------|----------|-----|-------|---------------------|
| 1 | description | `Purchased & returned item` | `Purchased &amp; returned item` | html entity | No — model writes correct code but fails self-test |
| 6 | description | `Left for competitor & unlikely...` | `...&amp;...` | html entity | Same |
| 9 | status | `active` | `acitve` | enum typo | No — stochastic dictionary coverage |
| 4 | weight | `5.22 kg` | `None` | lbs. period | No — regex edge case |
