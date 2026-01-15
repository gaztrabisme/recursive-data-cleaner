# TODO - Recursive Data Cleaner Roadmap

## Current Version: v0.5.0

344 tests passing, 2,575 lines. All planned tiers complete.

## Known Limitations

1. **Stateful ops within chunks only** - Deduplication, aggregations don't work globally
2. ~~**No runtime testing**~~ → Fixed in v0.2.0
3. ~~**Generation order = execution order**~~ → Fixed in v0.4.0
4. ~~**Redundant functions**~~ → Fixed in v0.5.0

---

## Tier 1: Low-Hanging Fruit ✅ COMPLETE (v0.2.0)

### Runtime Validation ✅
- [x] Test generated functions on sample data before accepting
- [x] Use `exec()` + `try/except` to catch `KeyError`, `TypeError`, etc.
- [x] Reject functions that fail at runtime, retry with error feedback
- **Implemented**: `recursive_cleaner/validation.py`

### Type/Schema Inference ✅
- [x] Sample first N records to detect field names and types
- [x] Add detected schema to prompt under `=== DATA SCHEMA ===` section
- [x] Helps LLM generate more accurate functions
- **Implemented**: `recursive_cleaner/schema.py`

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

## Tier 2: Meaningful Enhancements ✅ COMPLETE (v0.4.0)

### Validation Holdout ✅
- [x] Split each chunk: 80% for generation, 20% for testing
- [x] Run generated function on holdout data before accepting
- [x] Catch edge cases the LLM missed in training portion
- **Implemented**: `split_holdout()` in `validation.py`

### Dependency Resolution ✅
- [x] Use AST to detect which functions call which
- [x] Topological sort to order functions by dependencies
- [x] Ensure `normalize_phone()` runs before `validate_contact()` if needed
- **Implemented**: `recursive_cleaner/dependencies.py`

### Smart Sampling ✅
- [x] Random sampling vs sequential (current)
- [x] Stratified sampling for categorical fields
- [x] Deterministic seed from file hash for reproducibility
- **Implemented**: `sampling_strategy` param in `parsers.py`

### Quality Metrics ✅
- [x] Measure data quality before/after cleaning
- [x] Count: nulls, empty strings, unique values per field
- [x] Report improvement percentage
- **Implemented**: `recursive_cleaner/metrics.py`

---

## Tier 3: Bigger Bets ✅ PARTIAL (v0.5.0)

### Two-Pass Optimization ✅
- [x] First pass: generate functions (current behavior)
- [x] Second pass: LLM reviews all functions, consolidates/merges similar logic
- [x] IDF-based grouping for efficient batching
- [x] LLM agency: model decides when consolidation is complete
- **Implemented**: `recursive_cleaner/optimizer.py`

### Early Termination ✅
- [x] LLM detects when pattern discovery has saturated
- [x] Stop processing early to save time
- **Implemented**: `early_termination` param, `_check_saturation()` in `cleaner.py`

### Async Multi-Chunk Processing ❌ NOT PLANNED
- [ ] Process multiple chunks in parallel with asyncio
- [ ] Requires thread-safe function registry
- **Status**: Deferred - complexity not justified for current use cases

### Global State Awareness ❌ NOT PLANNED
- [ ] Cross-chunk deduplication tracking
- [ ] Aggregation support (counts, sums across full dataset)
- [ ] Shared state manager passed to generated functions
- **Status**: Deferred - would require architectural changes

---

## Philosophy Reminder

From CLAUDE.md:
- **Simplicity over extensibility** - Keep it lean
- **stdlib over dependencies** - Only tenacity required
- **Functions over classes** - Unless state genuinely helps
- **Delete over abstract** - No interfaces for single implementations
- **Retry over recover** - On error, retry with error in prompt
- **Wu wei** - Let the LLM make decisions about data it understands
