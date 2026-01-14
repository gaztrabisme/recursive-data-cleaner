# Success Criteria - Tier 1 Implementation

## Project-Level Success (v0.2.0)
- [ ] All 4 Tier 1 features implemented and tested
- [ ] Existing 79 tests still pass
- [ ] New tests for each feature
- [ ] Total codebase stays under 1000 lines (per philosophy)
- [ ] No new dependencies beyond stdlib

---

## Feature 1: Runtime Validation

### Deliverables
- [ ] `recursive_cleaner/validation.py` - Runtime testing module
- [ ] Integration into `cleaner.py` - Test functions before accepting
- [ ] Tests in `tests/test_validation.py`

### Success Criteria
- [ ] Generated function is executed on sample data before being added to registry
- [ ] Functions that raise `KeyError`, `TypeError`, `AttributeError` etc. are rejected
- [ ] Rejection triggers retry with error message in prompt
- [ ] Functions that return without error are accepted
- [ ] Test: function with `data["nonexistent_key"]` is rejected
- [ ] Test: function that works on sample data is accepted

### Verification Commands
```bash
pytest tests/test_validation.py -v
# Should show all validation tests passing
```

---

## Feature 2: Schema Inference

### Deliverables
- [ ] `recursive_cleaner/schema.py` - Schema inference module
- [ ] Integration into `prompt.py` - Add schema to prompt
- [ ] Tests in `tests/test_schema.py`

### Success Criteria
- [ ] Schema is inferred from first N records (default 10)
- [ ] Schema includes: field names, inferred types, sample values
- [ ] Schema is added to prompt under `=== DATA SCHEMA ===` section
- [ ] Works for JSONL, CSV, JSON array formats
- [ ] Test: JSONL with mixed types produces accurate schema
- [ ] Test: CSV headers become field names

### Verification Commands
```bash
pytest tests/test_schema.py -v
# Should show all schema tests passing
```

---

## Feature 3: Progress Callbacks

### Deliverables
- [ ] `on_progress` callback parameter added to `DataCleaner.__init__`
- [ ] Callback invoked at key points with structured data
- [ ] Tests in `tests/test_callbacks.py`

### Success Criteria
- [ ] `on_progress(event)` called with event dict containing:
  - `type`: "chunk_start" | "iteration" | "function_generated" | "chunk_done" | "complete"
  - `chunk_index`: int
  - `total_chunks`: int
  - `iteration`: int (when applicable)
  - `function_name`: str (when applicable)
- [ ] Callback is optional (None by default)
- [ ] Callback errors don't crash the pipeline (caught and logged)
- [ ] Test: callback receives correct sequence of events
- [ ] Test: callback exception doesn't stop processing

### Verification Commands
```bash
pytest tests/test_callbacks.py -v
# Should show all callback tests passing
```

---

## Feature 4: Incremental Saves

### Deliverables
- [ ] `state_file` parameter added to `DataCleaner.__init__`
- [ ] State saved after each chunk (JSON format)
- [ ] `resume_from` class method or parameter to continue from state
- [ ] Tests in `tests/test_incremental.py`

### Success Criteria
- [ ] State file contains: `functions`, `last_chunk_index`, `file_path`, `instructions`
- [ ] State saved to JSON after each chunk completes
- [ ] `DataCleaner.resume(state_file)` loads state and continues
- [ ] If state file exists and matches current file, resume automatically
- [ ] Test: interrupt and resume produces same result as uninterrupted run
- [ ] Test: state file is valid JSON with expected structure

### Verification Commands
```bash
pytest tests/test_incremental.py -v
# Should show all incremental save tests passing
```

---

## Integration Success Criteria

- [ ] All existing tests pass: `pytest tests/ -v` (79+ tests)
- [ ] New tests for Tier 1: `pytest tests/test_validation.py tests/test_schema.py tests/test_callbacks.py tests/test_incremental.py -v`
- [ ] Line count check: `find recursive_cleaner -name "*.py" | xargs wc -l` < 1000 total
- [ ] No new dependencies in `pyproject.toml` beyond `tenacity`
