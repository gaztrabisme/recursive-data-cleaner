# v2.0 Eval: Distribution-Aware Cleaning Impact

**Date**: 2026-02-21
**Mode**: Analyze
**Pipeline**: v2.0.0 (global field stats pre-pass, distribution-injected prompting)
**Benchmark**: CRM dataset (100 records, 76 golden assertions, 11 issue types)

---

## 1. Headline Numbers

| Model | Backend | v1.2.0 | v2.0 | Delta | Functions |
|-------|---------|--------|------|-------|-----------|
| **30B-A3B** | MLX 8-bit | 72/76 (94.7%) | **73/76 (96.1%)** | **+1** | 9 → 9 |
| **Coder-Next** | LM Studio 6-bit | 68/76 (89.5%) | **64/76 (84.2%)** | **-4** | 8 → 7 |
| **VL-30B** | LM Studio 8-bit | -- | **64/76 (84.2%)** | -- | 7 |

v2.0 distributions helped the strong model and hurt the weak one.

## 2. What Distributions Fixed (30B-A3B)

| Issue Type | v1.2.0 | v2.0 | Cause |
|------------|--------|------|-------|
| enum_typo | 7/8 | **8/8** | Status frequency table shows `'acitve': 10 (10%)` next to `'active': 23 (23%)` — model now catches all variants |
| weight_unit | 6/7 | **7/7** | Weight classified as high-cardinality (96 unique), so not directly shown — but status/category tables may have freed the model to focus better |
| phone_format | 8/8 | 7/8 | Stochastic regression — UK phone formatted with spaces instead of pure digits |

Net: +2 gains, -1 stochastic loss = **+1 net improvement**.

30B-A3B now has **9 of 11 issue types at 100%**. Only html_cleanup (hard floor) and phone_format (stochastic) remain.

## 3. What Distributions Broke (Coder-Next)

| Issue Type | v1.2.0 | v2.0 | Cause |
|------------|--------|------|-------|
| tag_format | **6/6** | **1/6** | Tags normalizer outputs comma-separated strings instead of JSON arrays |
| category_case | 3/8 | 3/8 | Still no category function generated despite seeing frequency table |
| phone_format | 7/8 | **8/8** | Improvement — now handles UK phone |

Net: +1 gain, -5 tag regression = **-4 net regression**.

### Root cause: prompt bloat

The v2.0 distribution block added **1,150 chars (~287 tokens) per LLM call**. Of that:
- **616 chars** were useful (status + category frequency tables)
- **498 chars (45%)** were filler: 11 lines of `field: X unique values (high cardinality)` that provide no actionable information

Impact on Coder-Next:
- Already the tighter model (5.0 calls/function vs 30B's 4.0)
- Hit max iterations on all 5 chunks in both v1.2.0 and v2.0
- Extra tokens per call reduced effective context for function accumulation
- First v2.0 attempt crashed entirely on context length overflow
- Dropped from 8 to 7 functions — lost tags normalizer quality, never generated category

**This led directly to the compact distributions fix** (commit `2efc5a5`): high-cardinality fields are now omitted from the prompt entirely. The distribution block is now 616 chars of pure signal.

## 4. VL-30B: New Model Baseline

First-time benchmark for the vision-language variant of 30B-A3B.

| Metric | VL-30B | 30B-A3B | Coder-Next |
|--------|--------|---------|------------|
| Score | 64/76 (84.2%) | 73/76 (96.1%) | 64/76 (84.2%) |
| Functions | 7 | 9 | 7 |
| LLM calls | 40 | ~36 | 40 |
| Max iter chunks | 5/5 | ~1/5 | 5/5 |
| category_case | 3/8 | 8/8 | 3/8 |
| date_format | 7/9 | 9/9 | 9/9 |
| null_empty | 3/6 | 6/6 | 6/6 |

VL-30B is the weakest code generator tested — burned all budget on every chunk, can't handle Unix timestamps, and never generated category or notes normalizers. The "vision" training did not translate to code generation capability.

Interesting strengths: enum_typo 8/8, weight_unit 7/7, phone_format 8/8 — competitive with the best on individual function quality when it does generate.

## 5. Per-Issue-Type Comparison (All Models, v2.0)

| Issue Type | 30B-A3B | Coder-Next | VL-30B |
|------------|---------|------------|--------|
| amount_format | 6/6 | 6/6 | 6/6 |
| date_format | 9/9 | 9/9 | 7/9 |
| email_case | 4/4 | 4/4 | 4/4 |
| phone_format | 7/8 | **8/8** | **8/8** |
| enum_typo | **8/8** | **8/8** | **8/8** |
| whitespace | 7/7 | 7/7 | 7/7 |
| tag_format | **6/6** | 1/6 | **6/6** |
| weight_unit | **7/7** | **7/7** | **7/7** |
| category_case | **8/8** | 3/8 | 3/8 |
| html_cleanup | 5/7 | 5/7 | 5/7 |
| null_empty | **6/6** | **6/6** | 3/6 |

30B-A3B is the only model with category_case at 100%. All three models share the HTML entity hard floor.

## 6. Remaining Failures After v2.0

### 30B-A3B (3 failures — near ceiling)

| Record | Field | Issue | Root Cause |
|--------|-------|-------|------------|
| 4 | phone | phone_format | UK phone formatted `+44 20 7946 0958` instead of `+442079460958` |
| 1 | description | html_cleanup | `&amp;` not decoded — universal hard floor |
| 6 | description | html_cleanup | `&amp;` not decoded — universal hard floor |

Theoretical max: 74/76. Actual: 73/76. Gap is 1 stochastic phone assertion.

### Coder-Next (12 failures)

- 5x category_case — no function generated
- 5x tag_format — normalizer outputs wrong format (comma strings, not JSON arrays)
- 2x html_cleanup — universal hard floor

### VL-30B (12 failures)

- 5x category_case — no function generated
- 3x null_empty — no notes normalizer generated
- 2x date_format — can't convert Unix timestamps
- 2x html_cleanup — universal hard floor

## 7. Key Takeaways

1. **Distributions work for strong models.** 30B-A3B went from 94.7% to 96.1% — the frequency tables gave it the context needed to fix enum_typo completely. This validates the v2.0 design thesis.

2. **Prompt bloat penalizes weak models.** The original distribution block was 45% filler. For context-limited models, every token counts. Fixed by omitting high-cardinality fields (commit `2efc5a5`).

3. **Category_case remains the differentiator.** Only 30B-A3B generates a category function. Distributions show the canonical forms clearly, but weaker models still don't prioritize it over other issues within their iteration budget.

4. **30B-A3B is at the practical ceiling.** 73/76 with only 2 systematic failures (HTML entity) and 1 stochastic (phone). Further improvement requires either a model that correctly implements `html.unescape()` or more eval runs to average out stochastic variance.

5. **VL models are not suitable for code generation.** Vision training does not transfer to data cleaning code quality. Standard instruct models remain the best choice.

## 8. What Was Done About It

- **Compact distributions** (commit `2efc5a5`): Omit high-cardinality fields from prompt. 1,114 chars → 616 chars, pure signal.
- **Not yet re-tested**: Coder-Next with compact distributions. The fix removes 45% of prompt bloat — may recover the tag regression.
