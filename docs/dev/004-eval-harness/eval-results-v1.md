# Eval Results v1: CRM Benchmark Golden Assertions

**Date**: 2026-02-19
**Harness**: `benchmarks/eval/run_eval.py`
**Dataset**: `benchmarks/benchmark_data.jsonl` (100 records, 13 fields)
**Assertions**: `benchmarks/eval/golden/benchmark_golden.jsonl` (76 assertions, 11 issue types)
**Pipeline version**: v1.1.0 (pre-composition-testing, pre-relevance-context)

> These cleaning function files were generated during the v1.0.3 benchmark runs.
> The eval harness was built after the fact — no models were re-run.

---

## Leaderboard

| Rank | Model | Score | % | Pipeline Time | Functions | Avg LLM Call |
|------|-------|-------|---|---------------|-----------|--------------|
| 1 | Qwen3-30B-A3B | **70/76** | **92.1%** | 9.8 min | 9 | 24s |
| 2 | Qwen3-Coder-30B-A3B | 66/76 | 86.8% | 6.3 min | 8 | 17s |
| 3 | Qwen3-4B | 58/76 | 76.3% | 12.8 min | 6 | 31s |
| 3 | Qwen3-Next-80B-A3B | 58/76 | 76.3% | 9.1 min | 6 | 22s |
| 5 | Qwen3-8B | 56/76 | 73.7% | 39.0 min | 7 | 93s |
| 6 | Qwen3-14B | 47/76 | 61.8% | 67.9 min | 4 | 163s |
| 7 | Qwen3-Coder-Next | 43/76 | 56.6% | 11.2 min | 4 | 27s |

## Per-Issue-Type Heatmap

| Issue Type | 30B-A3B | Coder-30B | 4B | Next-80B | 8B | 14B | Coder-Next |
|------------|---------|-----------|-------|----------|-------|-------|------------|
| amount_format | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 |
| date_format | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 8/9 | 9/9 |
| email_case | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 |
| phone_format | 8/8 | 8/8 | 8/8 | 8/8 | 7/8 | 8/8 | 1/8 |
| enum_typo | 8/8 | 8/8 | 8/8 | 7/8 | 4/8 | 2/8 | 7/8 |
| whitespace | 7/7 | 7/7 | 1/7 | 1/7 | 7/7 | 7/7 | 1/7 |
| tag_format | 6/6 | 6/6 | 6/6 | 6/6 | 1/6 | 1/6 | 1/6 |
| weight_unit | 6/7 | 7/7 | 5/7 | 6/7 | 7/7 | 0/7 | 3/7 |
| **category_case** | **8/8** | 3/8 | 3/8 | 3/8 | 3/8 | 3/8 | 3/8 |
| html_cleanup | 5/7 | 5/7 | 5/7 | 5/7 | 5/7 | 5/7 | 5/7 |
| null_empty | 3/6 | 3/6 | 3/6 | 3/6 | 3/6 | 3/6 | 3/6 |

## Functions Generated Per Model

| Model | # | Functions |
|-------|---|-----------|
| Qwen3-30B-A3B | 9 | normalize_dates, normalize_phone_numbers, normalize_names, **normalize_category_field**, normalize_amounts, normalize_whitespace, normalize_status_field, normalize_weight_field, normalize_tags_field |
| Qwen3-Coder-30B-A3B | 8 | normalize_date, normalize_phone, normalize_amount, clean_name_whitespace, fix_status_field, normalize_weight, normalize_tags, normalize_email |
| Qwen3-8B | 7 | normalize_date_joined, normalize_phone_number, normalize_amount, clean_name_field, fix_status, normalize_weight, normalize_email |
| Qwen3-4B | 6 | normalize_date, normalize_phone, normalize_amount, normalize_status, normalize_weight, normalize_tags |
| Qwen3-Next-80B-A3B | 6 | normalize_dates, normalize_amounts, normalize_phones, normalize_status, normalize_weights, normalize_tags |
| Qwen3-14B | 4 | normalize_date_joined, normalize_phone_number, normalize_amount, normalize_name_whitespace |
| Qwen3-Coder-Next | 4 | normalize_dates_iso8601, fix_status_typos, normalize_weight_to_kg, normalize_amounts_decimal |

---

## Key Findings

### 1. The 30B-A3B wins because it generates more functions, not because its functions are better

The 30B-A3B generated **9 functions** covering 9 of 11 issue categories. It's the only model that generated a category normalization function. Its winning margin (92.1% vs 86.8% for Coder-30B) comes entirely from `category_case` (8/8 vs 3/8 = +5 points).

Both models share the same 6 failures: 2x html_cleanup (entity decoding), 3x null_empty, 1x weight_unit.

### 2. Parameter count does not predict correctness

| Dense models | Score | MoE models | Score |
|-------------|-------|------------|-------|
| Qwen3-4B | 76.3% | Qwen3-30B-A3B | **92.1%** |
| Qwen3-8B | 73.7% | Qwen3-Next-80B-A3B | 76.3% |
| Qwen3-14B | 61.8% | Qwen3-Coder-30B-A3B | 86.8% |
| | | Qwen3-Coder-Next | 56.6% |

The 4B model ties with the 80B model. The 14B model (61.8%) is beaten by the 4B (76.3%). The dense models show an **inverted** scaling curve.

### 3. Instruction-following quality > raw capability

The 14B generated only 4 functions in 67.9 minutes. It spent 163s per LLM call — likely hitting thinking token limits or producing verbose, unfocused output. The 4B generated 6 functions in 12.8 min at 31s per call and beat it by 15 points.

The 30B-A3B generated 9 functions in 9.8 min at 24s per call. Fast, focused, comprehensive.

### 4. Three universal blind spots (no model solves these)

**HTML entity decoding** (5/7 for all models):
- `&amp;` → `&` not handled. All models fail on records 1 and 6 where description contains `&amp;` without surrounding HTML tags. Models likely generate tag-stripping functions but miss standalone entity decoding.

**Null/empty normalization** (3/6 for all models):
- Empty strings `""` and whitespace-only `"   "` are not converted to `null` in the notes field. Every model fails on records 1, 3, and 6. No model generates a null-normalization function.

**Category case normalization** (3/8 for 6 of 7 models):
- Only the 30B-A3B generates a category normalizer. Other models focus on higher-signal issues (dates, phones, amounts) and never get to category case.

### 5. The 4-bit quantization tax

Both 4-bit models underperform their 8-bit counterparts:
- Coder-Next (4-bit): 56.6% — worst overall, generates only 4 functions, misses phone formatting entirely
- Next-80B-A3B (4-bit): 76.3% — ties with 4B (8-bit), but should dominate given 80B params

The 4-bit models appear to lose instruction-following precision. Coder-Next in particular generates a phone normalization function that doesn't actually work (1/8).

### 6. Coder models are not better at generating data cleaning code

| Base model | Score | Coder variant | Score | Delta |
|-----------|-------|---------------|-------|-------|
| Qwen3-30B-A3B | 92.1% | Qwen3-Coder-30B-A3B | 86.8% | -5.3% |
| — | — | Qwen3-Coder-Next | 56.6% | — |

The Coder-30B loses to its base variant despite being a "code-specialized" model. Data cleaning is an instruction-following task, not a code generation task.

---

## Failure Taxonomy

### Failures unique to bottom models (not shared with 30B-A3B)

| Failure | Affected Models | Root Cause |
|---------|-----------------|------------|
| No status typo correction | 14B (6/8 fail), 8B (4/8 fail) | No `fix_status` function generated |
| No tag normalization | 14B, 8B, Coder-Next (5/6 fail each) | No `normalize_tags` function generated |
| No whitespace normalization | 4B, Next-80B, Coder-Next (6/7 fail each) | No `clean_name` function generated |
| No weight conversion | 14B (7/7 fail) | No `normalize_weight` function generated |
| No phone normalization | Coder-Next (7/8 fail) | Function exists but doesn't convert formats |
| No category normalization | All except 30B-A3B (5/8 fail each) | No `normalize_category` function generated |

### Failures shared by ALL models (systemic)

| Failure | Records | Root Cause |
|---------|---------|------------|
| `&amp;` not decoded to `&` | 1, 6 | Entity decoding not triggered without surrounding tags |
| Empty/whitespace notes not nulled | 1, 3, 6 | No model generates a null-normalization function |

### 30B-A3B only failures (6 total)

| Failure | Record | Expected | Got | Root Cause |
|---------|--------|----------|-----|------------|
| html entity | 1 | `Purchased & returned item` | `Purchased &amp; returned item` | Entity decoding gap |
| html entity | 6 | `Left for competitor & unlikely to return` | `...&amp;...` | Same |
| weight lbs. | 4 | `5.22 kg` | `11.5 lbs.` | Trailing period in "lbs." not handled |
| null_empty | 1 | `null` | `""` | Empty string not nulled |
| null_empty | 3 | `null` | `""` | Same |
| null_empty | 6 | `null` | `""` | Same |

---

## Implications for Pipeline Development

1. **Prompt engineering opportunity**: The universal blind spots (entity decoding, null normalization) suggest the prompt template should explicitly mention these patterns. Currently the instructions mention "Strip HTML tags and decode HTML entities" but models only strip tags.

2. **Iteration budget matters**: The 30B-A3B generated 9 functions, meaning it needed at least 9 productive iterations. Models that generate fewer functions likely hit the adaptive iteration budget (2 fruitless → skip) before covering all issues. The v1.1.0 efficiency features may be too aggressive for models that need more exploration time.

3. **Category normalization as a litmus test**: Only 1/7 models covers this. It's a mid-priority issue that requires the model to notice case inconsistencies and generate a Title Case function. Good test of whether the pipeline reaches "long tail" issues.

4. **Quantization trade-off is real**: 4-bit models save memory but lose correctness. For benchmark runs, 8-bit is the minimum viable quantization.

5. **amount_format assertions need tightening**: All models score 100% on amount_format because `numeric_close` extracts the numeric value from any format (even uncleaned `"$1,234.56"` parses to 1234.56). Consider adding exact-match assertions for amounts to detect whether the format was actually cleaned.

---

## Methodology Notes

- **No re-running**: All cleaning function files come from the v1.0.3 benchmark suite. The eval harness evaluates pre-generated output.
- **Match modes**: `exact` (default), `numeric_close` (weight conversions, amounts), `contains` (HTML cleanup where whitespace/newline handling varies).
- **amount_format caveat**: `numeric_close` on amounts will pass even if the value hasn't been cleaned, as long as the underlying number is correct. This inflates amount_format scores for models that don't generate amount-cleaning functions. All models do generate amount functions, so this doesn't affect the rankings, but it's a known limitation.
- **"Already clean" assertions**: ~15 of 76 assertions test values that are already correct in the source data. These verify models don't over-fix (e.g., corrupt a valid phone number). All models pass these, confirming idempotency.
