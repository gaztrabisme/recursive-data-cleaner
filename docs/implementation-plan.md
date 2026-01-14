# Implementation Plan - Tier 1 Features

## Overview
Add 4 low-complexity features to the Recursive Data Cleaner: runtime validation, schema inference, progress callbacks, and incremental saves. Target: v0.2.0.

## Technology Stack
| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Existing |
| Dependencies | stdlib only | Philosophy: no new deps |
| Serialization | JSON | stdlib, human-readable |
| Testing | pytest | Existing |

---

## Phase 1: Runtime Validation

**Objective:** Test generated functions on sample data before accepting them.

**Deliverables:**
- [ ] `recursive_cleaner/validation.py` (~40 lines)
- [ ] Updates to `recursive_cleaner/cleaner.py` (~15 lines)
- [ ] `tests/test_validation.py` (~60 lines)

**Success Criteria:**
- [ ] `validate_function()` returns `(True, None)` for working functions
- [ ] `validate_function()` returns `(False, "KeyError: 'x'")` for broken functions
- [ ] Cleaner retries with error when validation fails
- [ ] All existing tests pass

**Implementation Notes:**
- Use `exec()` to compile function in isolated namespace
- Extract sample data from chunk (first 3 JSON objects)
- Catch all exceptions, format as error message
- Integrate between `parse_response()` and `functions.append()`

**Estimated Complexity:** Low

**Dependencies:** None

---

## Phase 2: Schema Inference

**Objective:** Detect data schema and include it in prompts for better LLM context.

**Deliverables:**
- [ ] `recursive_cleaner/schema.py` (~70 lines)
- [ ] Updates to `recursive_cleaner/prompt.py` (~10 lines)
- [ ] Updates to `recursive_cleaner/cleaner.py` (~5 lines)
- [ ] `tests/test_schema.py` (~80 lines)

**Success Criteria:**
- [ ] `infer_schema()` correctly identifies fields from JSONL/CSV/JSON
- [ ] `format_schema_for_prompt()` produces readable output
- [ ] Prompt includes schema section
- [ ] All existing tests pass

**Implementation Notes:**
- Parse first N records using existing `parsers.py` logic
- Union all keys found, infer types by checking values
- Keep sample values (3 per field) for LLM context
- New prompt section: `=== DATA SCHEMA ===`

**Estimated Complexity:** Low-Medium

**Dependencies:** None (can run parallel with Phase 1)

---

## Phase 3: Progress Callbacks

**Objective:** Allow users to receive real-time progress updates.

**Deliverables:**
- [ ] Updates to `recursive_cleaner/cleaner.py` (~25 lines)
- [ ] `tests/test_callbacks.py` (~50 lines)

**Success Criteria:**
- [ ] Callback receives events at chunk start, iteration, function generated, chunk done
- [ ] Callback errors are caught and logged, don't crash pipeline
- [ ] `on_progress=None` (default) works silently
- [ ] All existing tests pass

**Implementation Notes:**
- Add `_emit()` helper method that wraps callback safely
- Event dict structure defined in contract
- Use `try/except` around callback invocation

**Estimated Complexity:** Low

**Dependencies:** None (can run parallel with Phase 1 & 2)

---

## Phase 4: Incremental Saves

**Objective:** Save state after each chunk, allow resume on interruption.

**Deliverables:**
- [ ] Updates to `recursive_cleaner/cleaner.py` (~50 lines)
- [ ] `tests/test_incremental.py` (~80 lines)

**Success Criteria:**
- [ ] State saved to JSON after each chunk completes
- [ ] `DataCleaner.resume(state_file, backend)` loads and continues
- [ ] Interrupted run + resume = same result as uninterrupted
- [ ] Invalid state file raises clear error
- [ ] All existing tests pass

**Implementation Notes:**
- Save state with `json.dump()` after each chunk
- On init, if `state_file` exists, load and skip completed chunks
- Use `tempfile` in tests to avoid file conflicts
- Atomic write: write to `.tmp`, then rename

**Estimated Complexity:** Medium

**Dependencies:** Phase 1-3 (needs stable cleaner.py before adding state)

---

## Phase 5: Integration & Polish

**Objective:** Ensure all features work together, update docs.

**Deliverables:**
- [ ] Integration test combining all features
- [ ] Updated README.md with new features
- [ ] Updated CLAUDE.md version to v0.2.0
- [ ] Updated TODO.md (mark Tier 1 complete)

**Success Criteria:**
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Line count < 1000: `find recursive_cleaner -name "*.py" | xargs wc -l`
- [ ] Example in README works

**Estimated Complexity:** Low

**Dependencies:** Phases 1-4

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| exec() security | Low | Medium | Only runs on LLM-generated code, which is already trusted |
| State file corruption | Low | Medium | Atomic writes, version field for validation |
| Callback performance | Low | Low | Callbacks are optional, O(1) per event |
| Schema inference edge cases | Medium | Low | Fallback to empty schema for unknown formats |

## Out of Scope
- Async/parallel processing (Tier 3)
- Global state awareness (Tier 3)
- Dependency resolution (Tier 2)
- Quality metrics (Tier 2)

---

## Execution Strategy

Phases 1-3 are independent and can be implemented in parallel via subagents.
Phase 4 depends on stable cleaner.py, so runs after 1-3 complete.
Phase 5 is final integration.

```
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Phase 1 │  │ Phase 2 │  │ Phase 3 │
│Validation│  │ Schema  │  │Callbacks│
└────┬────┘  └────┬────┘  └────┬────┘
     │            │            │
     └────────────┼────────────┘
                  │
            ┌─────▼─────┐
            │  Phase 4  │
            │Incremental│
            └─────┬─────┘
                  │
            ┌─────▼─────┐
            │  Phase 5  │
            │Integration│
            └───────────┘
```
