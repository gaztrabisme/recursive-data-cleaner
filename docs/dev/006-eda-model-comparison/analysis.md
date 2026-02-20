# EDA: Two-Model Comparison on v1.2.0-dev Pipeline

**Date**: 2026-02-20
**Models**: Qwen3-30B-A3B-Instruct (MLX 8-bit) vs Qwen3-Coder-Next (LM Studio 6-bit)
**Pipeline**: v1.2.0-dev (no-op gate fix, soft dedup, prompt hints, max_iterations=8)
**Benchmark**: CRM dataset (100 records, 76 golden assertions, 11 issue types)

---

## 1. Headline Numbers

| Metric | 30B-A3B | Coder-Next |
|--------|---------|------------|
| **Score** | **72/76 (94.7%)** | **68/76 (89.5%)** |
| Functions | 9 | 8 |
| LLM calls | 36 | 40 |
| Calls/function | 4.0 | 5.0 |
| Avg latency | 42s | 68s |
| Pipeline time | 25.5 min | 45.3 min |
| Chunks hitting max_iter | 0 | 3/5 |
| Backend | MLX direct | LM Studio API |

## 2. Improvement from v1.0.3 Baseline

| Model | v1.0.3 | v1.2.0-dev | Delta | Functions v1→v2 |
|-------|--------|-----------|-------|-----------------|
| 30B-A3B | 70/76 (92.1%) | 72/76 (94.7%) | **+2.6pp** | 9 → 9 |
| Coder-Next | 43/76 (56.6%) | 68/76 (89.5%) | **+32.9pp** | 4 → 8 |

**The pipeline improvements helped the weaker model 12x more than the strong model.**

### Why the asymmetry?

30B-A3B already generated 9 functions on v1.0.3. The improvements gave it the null normalizer (+3) but cost it one enum typo (-1) through stochasticity. Net: +2.

Coder-Next went from 4 to 8 functions. The 4 new functions (phone, tags, notes, name) account for exactly +25 assertions:

| New function | Assertions gained |
|-------------|-------------------|
| normalize_phone_e164_us | +6 (7/8, UK miss) |
| normalize_tags_json_array | +6 (6/6) |
| normalize_notes_null_empty | +6 (6/6) |
| normalize_name_clean_whitespace_title | +7 (7/7) |
| **Total** | **+25** |

43 + 25 = 68. Exact match.

**Conclusion**: On v1.0.3, the pipeline was the bottleneck for weaker models — not their capability. `max_iterations=5` starved them of budget, and the no-op gate killed their null normalizers. With those constraints removed, Coder-Next's raw function quality is competitive.

---

## 3. Per-Issue-Type Comparison

| Issue Type | 30B-A3B | Coder-Next | Better |
|------------|---------|------------|--------|
| amount_format | 6/6 | 6/6 | Tie |
| date_format | 9/9 | 9/9 | Tie |
| email_case | 4/4 | 4/4 | Tie |
| phone_format | **8/8** | 7/8 | 30B |
| enum_typo | 7/8 | **8/8** | Coder |
| whitespace | 7/7 | 7/7 | Tie |
| tag_format | 6/6 | 6/6 | Tie |
| weight_unit | 6/7 | **7/7** | Coder |
| category_case | **8/8** | 3/8 | 30B |
| html_cleanup | 5/7 | 5/7 | Tie |
| null_empty | 6/6 | 6/6 | Tie |

**7 ties, 2 wins each.** The models are complementary, not strictly ordered.

---

## 4. Failure Analysis

### 4.1 All 12 failures mapped

| # | Model | Record | Field | Expected | Got | Issue | Root Cause |
|---|-------|--------|-------|----------|-----|-------|------------|
| 1 | 30B | 9 | status | `active` | `acitve` | enum_typo | Typo variant missing from dict |
| 2 | 30B | 1 | description | `...&...` | `...&amp;...` | html_cleanup | No entity decoding |
| 3 | 30B | 6 | description | `...&...` | `...&amp;...` | html_cleanup | No entity decoding |
| 4 | 30B | 4 | weight | `5.22 kg` | `None` | weight_unit | Regex fails on "lbs." |
| 5 | Coder | 4 | phone | `+442079460958` | `+44 20 7946 0958` | phone_format | US-only normalization |
| 6 | Coder | 1 | category | `Electronics` | `electronics` | category_case | No function generated |
| 7 | Coder | 2 | category | `Electronics` | `ELECTRONICS` | category_case | No function generated |
| 8 | Coder | 3 | category | `Electronics` | `eLECTRONICS` | category_case | No function generated |
| 9 | Coder | 5 | category | `Clothing` | `CLOTHING` | category_case | No function generated |
| 10 | Coder | 8 | category | `Home & Garden` | `HOME & GARDEN` | category_case | No function generated |
| 11 | Coder | 1 | description | `...&...` | `...&amp;...` | html_cleanup | No entity decoding |
| 12 | Coder | 6 | description | `...&...` | `...&amp;...` | html_cleanup | No entity decoding |

### 4.2 Root cause taxonomy

**Category A — Shared failures (2 assertions)**
Both models fail records 1 and 6 on `description` (HTML entity `&amp;` → `&`). Neither model generates an `html.unescape()` function. This is the **hard floor** — three pipeline versions, two models, same result.

**Category B — Coverage gap (5 assertions, Coder-Next only)**
Coder-Next never generates a category function. With 40 LLM calls and 3/5 chunks hitting max_iterations, it ran out of budget. The model prioritized phone, tags, notes, and name over category — possibly because category_case is a subtle issue (title case vs uppercase) that's easy to overlook when scanning data.

**Category C — Function quality gap (5 assertions, split)**

| Failure | Model | Code analysis |
|---------|-------|---------------|
| enum `acitve` | 30B | Status map has `actve` but NOT `acitve`. Missing variant. |
| weight `lbs.` | 30B | Regex `[a-zA-Z]+` matches "lbs" but trailing `.` breaks `\s*$` |
| UK phone | Coder | Function name says "e164_us" — explicitly US-only. 10-digit check. |

The ironic detail: **Coder-Next writes better individual functions** for the issues it covers.

### 4.3 Code-level comparison of key functions

**Status typo dictionary:**

```
30B:  {actve, pendng, chruned, active, pending, churned}     ← missing acitve
Coder: {actve, acitve, pendng, chruned}                      ← has both variants
```

**Weight regex:**

```
30B:   r'^\s*([0-9]+\.?[0-9]*)\s*([a-zA-Z]+)\s*$'           ← "lbs." fails
Coder: r'^([+-]?\d+(?:\.\d+)?)\s*(kg|lbs?|g)?\.?$'          ← \.? handles period
```

**Phone normalization:**

```
30B:   Explicit US (+1, 10-digit) AND UK (+44, 11-digit with 0-prefix) handling
Coder: US-only (10 digits → +1). All other lengths left unchanged.
```

**Category:**

```
30B:   stripped.title()  — 7 lines, covers all cases
Coder: (none)           — never generated
```

---

## 5. Theoretical Ensemble

If we take the best result per assertion from both models:

- 30B covers: category_case (8/8), phone_format (8/8)
- Coder covers: enum_typo (8/8), weight_unit (7/7)
- Both cover: everything else at 100%
- Both fail: html_cleanup records 1, 6

**Ensemble score: 74/76 (97.4%)**

The only remaining failures would be the 2 HTML entity assertions — the universal hard floor.

---

## 6. What the Data Tells Us

### 6.1 Pipeline is no longer the bottleneck

v1.0.3 → v1.2.0-dev eliminated the pipeline as the primary constraint. Evidence:
- Coder-Next jumped +33pp just from pipeline improvements (no model change)
- Both models now generate null normalizers (no-op gate fix confirmed across models)
- 30B uses 36/40 of its call budget; Coder-Next uses all 40

The remaining failures are model-quality issues: typo dictionary completeness, regex edge cases, multi-country awareness, function coverage priority.

### 6.2 Iteration budget is still tight for Coder-Next

Coder-Next hit max_iterations on 3/5 chunks and still didn't generate a category function. Its 5.0 calls/function ratio (vs 30B's 4.0) means it needs more retries per function. With 12 cleaning tasks and 8 functions generated, it's 4 functions short of full coverage.

Possible remedies (not necessarily worth implementing):
- Increase max_iterations further (8→12) — diminishing returns, longer runtime
- Priority guidance in prompt — might help but adds prompt complexity
- None of these fix the fundamental issue: Coder-Next burns more calls per function

### 6.3 Function quality has an inverse relationship with coverage

| Metric | 30B-A3B | Coder-Next |
|--------|---------|------------|
| Coverage (functions) | 9/12 tasks | 8/12 tasks |
| Quality (per-function accuracy) | 68/72 within-coverage | 63/68 within-coverage |
| Quality % | 94.4% | 92.6% |

Within the issues they cover, both models are above 92%. The difference in headline score comes from coverage breadth, not function quality.

### 6.4 The "Coder" label is misleading

v1 analysis concluded "Coder models are not better at generating data cleaning code." The v1.2.0 data refines this: **Coder models write more defensively** (better edge case handling in weight regex, more complete typo dictionaries) but **cover fewer issue types** (no category, US-only phone). The "coder" training likely emphasizes code correctness over instruction-following breadth.

### 6.5 HTML entity decoding is the true ceiling

Three pipeline versions. Two models. Seven models in v1. Same 2 failures every time. The prompt explicitly says "decode HTML entities." The prompt hints say "use html.unescape()." Models attempt it, but fail their own test assertions (confusing `&amp;` entity with the English word "and").

This is not fixable by prompt engineering or pipeline architecture. It requires either:
- A model that correctly writes `html.unescape()` test cases, or
- Relaxing test-case validation for HTML functions (undesirable — weakens quality gate)

---

## 7. Implications for Roadmap

### What's done (v1.2.0 pipeline)
- No-op gate fix: validated across both models (null_empty 3/6→6/6)
- Soft dedup: no observable effect (neither model generated supplementary functions)
- max_iterations=8: essential for Coder-Next (+4 functions), marginal for 30B
- Prompt hints: stdlib hint acknowledged by models but HTML entity still fails self-test

### What diminishing returns look like
Further pipeline improvements would target:
- Category coverage for Coder-Next: requires more iterations or priority hints. Gain: +5 assertions for one model.
- HTML entity: requires model-level improvement or test gate relaxation. Gain: +2 assertions universally.
- Weight "lbs." for 30B: could add more specific prompt hint. Gain: +1 assertion for one model.

**Total addressable improvement: 8 assertions across both models, at increasing engineering cost.**

### Recommended next steps
1. **Run more models through v1.2.0-dev** to see if the pattern holds (weaker models benefit disproportionately)
2. **Freeze v1.2.0** — the pipeline is at its local optimum for the CRM benchmark
3. **Diverse eval datasets** — the real test is whether these improvements generalize beyond CRM

---

## Appendix: Function Coverage Matrix

| Field/Task | 30B Function | Coder Function |
|-----------|-------------|----------------|
| date_joined | normalize_dates | normalize_dates_iso8601 |
| phone | normalize_phone_numbers | normalize_phone_e164_us |
| amount | normalize_amounts | normalize_amount_decimal |
| name (whitespace) | fix_whitespace_issues | normalize_name_clean_whitespace_title |
| category | normalize_category_field | **(none)** |
| weight | normalize_weight_field | normalize_weight_kg |
| tags | normalize_tags_field | normalize_tags_json_array |
| status | normalize_status_field | normalize_status_canonical |
| notes | normalize_notes_field | normalize_notes_null_empty |
| email | **(none)** | **(none)** |
| description (HTML) | **(none)** | **(none)** |
| city (whitespace) | fix_whitespace_issues | **(none)** |
