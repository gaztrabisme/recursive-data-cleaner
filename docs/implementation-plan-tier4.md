# Implementation Plan - Tier 4: Polish & Observability

## Overview

Four low-effort features following established patterns: AST manipulation, event emission, simple data aggregation.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Existing |
| Dependencies | stdlib + tenacity | No new deps |
| Patterns | AST walking, event emission | Proven in v0.5.x |

---

## Phase Breakdown

### Phase 1: Latency Metrics

**Objective:** Track timing of all LLM calls and report stats.

**Deliverables:**
- [ ] `cleaner.py`: Add `_latency_stats` dict to `__init__`
- [ ] `cleaner.py`: Wrap LLM calls with timing in `_process_chunk`
- [ ] `cleaner.py`: Emit `llm_call` event with `latency_ms`
- [ ] `cleaner.py`: Include stats in `complete` event
- [ ] `tests/test_latency.py`: 4-5 tests

**Success Criteria:**
- [ ] `pytest tests/test_latency.py -v` passes
- [ ] Mock LLM with 100ms delay shows ~100ms latency captured

**Estimated Complexity:** Low (~30 lines)

**Dependencies:** None

---

### Phase 2: Import Consolidation

**Objective:** Merge duplicate and related imports in output file.

**Deliverables:**
- [ ] `output.py`: Replace `deduplicate_imports()` with `consolidate_imports()`
- [ ] `output.py`: Handle `from x import a, b` merging
- [ ] `tests/test_output.py`: Extend with 4-5 import consolidation tests

**Success Criteria:**
- [ ] `pytest tests/test_output.py -v -k import` passes
- [ ] Output file has single import block, alphabetically sorted

**Estimated Complexity:** Low (~50 lines)

**Dependencies:** None

---

### Phase 3: Cleaning Report

**Objective:** Generate markdown summary of cleaning run.

**Deliverables:**
- [ ] `recursive_cleaner/report.py`: New module (~60 lines)
- [ ] `cleaner.py`: Add `report_path` parameter
- [ ] `cleaner.py`: Call `generate_report()` at end of `run()`
- [ ] `tests/test_report.py`: 4-5 tests

**Success Criteria:**
- [ ] `pytest tests/test_report.py -v` passes
- [ ] Report contains all required sections per contract

**Estimated Complexity:** Low (~80 lines total)

**Dependencies:** Phase 1 (for latency stats in report)

---

### Phase 4: Dry-Run Mode

**Objective:** Analyze data without generating functions.

**Deliverables:**
- [ ] `cleaner.py`: Add `dry_run` parameter
- [ ] `cleaner.py`: Modify `_process_chunk` to skip function storage when dry_run
- [ ] `cleaner.py`: Add `issues_detected` event emission
- [ ] `cleaner.py`: Skip `_write_output()` when dry_run
- [ ] `tests/test_dry_run.py`: 4-5 tests

**Success Criteria:**
- [ ] `pytest tests/test_dry_run.py -v` passes
- [ ] Dry run produces no output file
- [ ] Events show issues detected

**Estimated Complexity:** Low (~40 lines)

**Dependencies:** None

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Import merging edge cases | Medium | Low | Comprehensive tests, keep both on conflict |
| Report format changes | Low | Low | Keep simple, avoid over-engineering |

## Out of Scope

- Async/parallel processing
- Custom report templates
- Latency percentiles (p50, p99)
- Issue deduplication algorithm

---

## Execution Order

1. **Phase 1: Latency** (no deps, foundational for report)
2. **Phase 2: Imports** (no deps, isolated change)
3. **Phase 3: Report** (uses latency stats)
4. **Phase 4: Dry-Run** (no deps, uses existing events)

Phases 1, 2, and 4 can be implemented in parallel. Phase 3 waits for Phase 1.

---

## Estimated Total

- **New lines**: ~150-200
- **New tests**: ~18-20
- **New files**: 2 (`report.py`, `test_report.py`, `test_latency.py`, `test_dry_run.py`)
