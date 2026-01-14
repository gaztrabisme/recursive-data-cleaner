# TODO - Recursive Data Cleaner Roadmap

## Current Version: v0.1.0

Working implementation with 79 tests passing. Generates valid Python cleaning functions from messy data using LLM-powered analysis.

## Known Limitations

1. **No runtime testing** - Validates syntax but doesn't actually run generated functions
2. **Stateful ops within chunks only** - Deduplication, aggregations don't work globally
3. **Generation order = execution order** - No dependency resolution between functions

---

## Tier 1: Low-Hanging Fruit ✅ COMPLETE (v0.2.0)

### Runtime Validation ✅
- [x] Test generated functions on sample data before accepting
- [x] Use `exec()` + `try/except` to catch `KeyError`, `TypeError`, etc.
- [x] Reject functions that fail at runtime, retry with error feedback
- **Implemented**: `recursive_cleaner/validation.py` (72 lines)

### Type/Schema Inference ✅
- [x] Sample first N records to detect field names and types
- [x] Add detected schema to prompt under `=== DATA SCHEMA ===` section
- [x] Helps LLM generate more accurate functions
- **Implemented**: `recursive_cleaner/schema.py` (117 lines)

### Progress Callbacks ✅
- [x] Add optional `on_progress` callback to `DataCleaner`
- [x] Report: chunk index, iteration, function generated, status
- [x] Useful for 500MB files that take hours
- **Implemented**: `_emit()` method in `cleaner.py`

### Incremental Saves ✅
- [x] Save state (functions list) between chunks
- [x] Add `state_file` parameter and `resume()` classmethod
- [x] JSON serialization with atomic writes
- **Implemented**: `_save_state()`, `_load_state()`, `resume()` in `cleaner.py`

---

## Tier 2: Meaningful Enhancements (~100-200 lines)

### Validation Holdout
- [ ] Split each chunk: 80% for generation, 20% for testing
- [ ] Run generated function on holdout data before accepting
- [ ] Catch edge cases the LLM missed in training portion
- **Value**: Better coverage of data variations

### Dependency Resolution
- [ ] Use AST to detect which functions call which
- [ ] Topological sort to order functions by dependencies
- [ ] Ensure `normalize_phone()` runs before `validate_contact()` if needed
- **Value**: Correct execution order for dependent functions

### Smart Sampling
- [ ] Random sampling vs sequential (current)
- [ ] Stratified sampling for categorical fields
- [ ] Outlier detection to ensure edge cases are seen
- **Value**: See more data variety in fewer chunks

### Quality Metrics
- [ ] Measure data quality before/after cleaning
- [ ] Count: nulls, invalid formats, duplicates, outliers
- [ ] Report improvement percentage
- **Value**: Quantifiable proof that cleaning worked

---

## Tier 3: Bigger Bets (~200+ lines)

### Two-Pass Optimization
- [ ] First pass: generate functions (current behavior)
- [ ] Second pass: LLM reviews all functions, consolidates/merges similar logic
- [ ] Reduce redundancy (e.g., multiple date normalizers → one)
- **Value**: Cleaner, more maintainable output

### Async Multi-Chunk Processing
- [ ] Process multiple chunks in parallel with asyncio
- [ ] Requires thread-safe function registry
- [ ] Merge results at end
- **Value**: Faster processing for large datasets (if LLM supports concurrent calls)

### Global State Awareness
- [ ] Cross-chunk deduplication tracking
- [ ] Aggregation support (counts, sums across full dataset)
- [ ] Shared state manager passed to generated functions
- **Value**: Solves "stateful ops within chunks only" limitation

---

## Recommended v0.2.0 Scope

Priority upgrades that maximize value while respecting lean philosophy:

1. **Runtime validation** - Biggest bang for buck
2. **Schema inference** - Better LLM context = better output
3. **Validation holdout** - Catch edge cases automatically

These three together catch most "looks valid but doesn't work" cases.

---

## Philosophy Reminder

From CLAUDE.md:
- **Simplicity over extensibility** - Keep it under 1000 lines total
- **stdlib over dependencies** - No new deps unless absolutely necessary
- **Functions over classes** - Unless state genuinely helps
- **Delete over abstract** - No interfaces for single implementations
- **Retry over recover** - On error, retry with error in prompt
