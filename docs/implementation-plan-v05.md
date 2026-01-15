# Implementation Plan: Two-Pass Optimization (v0.5.0)

## Overview

Add LLM-powered function consolidation with agency - the model decides when optimization is complete.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Grouping | IDF (stdlib `math.log`) | No dependencies, principled IR technique |
| XML parsing | `xml.etree` | Already used in response.py |
| Agency | Self-assessment in prompts | LLM decides, not hardcoded rules |

---

## Phase 1: Tag Generation

**Objective:** Modify prompts so generated functions include semantic tags.

**Deliverables:**
- [ ] Update `recursive_cleaner/prompt.py` - add tag instruction to templates
- [ ] Add `extract_tags()` function to new `recursive_cleaner/optimizer.py`
- [ ] `tests/test_optimizer.py` (tag extraction tests)

**Success Criteria:**
- [ ] `PROMPT_TEMPLATE` includes tag instruction
- [ ] `TEXT_PROMPT_TEMPLATE` includes tag instruction
- [ ] `extract_tags("...Tags: date, normalize...")` returns `{"date", "normalize"}`
- [ ] `extract_tags("no tags here")` returns `set()`
- [ ] 5+ tests pass

**Complexity:** Low

**Dependencies:** None

---

## Phase 2: IDF-Based Grouping

**Objective:** Group functions by most informative tag for batch consolidation.

**Deliverables:**
- [ ] Add `group_by_salience()` to `recursive_cleaner/optimizer.py`
- [ ] Add `_rebalance_groups()` helper
- [ ] Add `_fallback_from_name()` helper
- [ ] Expand `tests/test_optimizer.py`

**Success Criteria:**
- [ ] Functions grouped by highest-IDF tag
- [ ] Groups < 2 functions merged into nearest neighbor
- [ ] Groups > 40 functions split
- [ ] Untagged functions use name-based fallback
- [ ] 10+ tests pass

**Complexity:** Medium

**Dependencies:** Phase 1 (needs `extract_tags`)

---

## Phase 3: Consolidation with Agency

**Objective:** LLM reviews function groups and merges redundant ones, deciding when complete.

**Deliverables:**
- [ ] Add `CONSOLIDATION_TEMPLATE` to `recursive_cleaner/prompt.py`
- [ ] Add `consolidate_group()` to `recursive_cleaner/optimizer.py`
- [ ] Add `consolidate_with_agency()` - the agency loop
- [ ] Add `AgentAssessment` dataclass
- [ ] Add `parse_consolidation_response()` to `recursive_cleaner/response.py`
- [ ] Expand `tests/test_optimizer.py`

**Success Criteria:**
- [ ] Consolidation prompt follows contract format
- [ ] `parse_consolidation_response()` extracts merged functions + assessment
- [ ] Agency loop terminates on `complete=true`
- [ ] Agency loop terminates at `max_rounds` (safety)
- [ ] Merged functions have valid Python syntax
- [ ] 10+ tests pass

**Complexity:** Medium-High

**Dependencies:** Phase 2 (needs grouped functions)

---

## Phase 4: Integration

**Objective:** Wire optimization into DataCleaner with proper callbacks.

**Deliverables:**
- [ ] Add `optimize`, `optimize_threshold` params to `DataCleaner.__init__`
- [ ] Add `_optimize_functions()` method to `DataCleaner`
- [ ] Add optimization event types to callback system
- [ ] Update `run()` to call optimization when enabled
- [ ] Integration tests in `tests/test_optimizer.py`

**Success Criteria:**
- [ ] `optimize=True` triggers two-pass after chunk processing
- [ ] Optimization skipped if `len(functions) < optimize_threshold`
- [ ] Progress callbacks fire for optimization events
- [ ] End-to-end test reduces function count
- [ ] 5+ tests pass

**Complexity:** Medium

**Dependencies:** Phase 3

---

## Phase 5: Early Termination (Optional)

**Objective:** LLM decides if chunk processing should stop early.

**Deliverables:**
- [ ] Add `SATURATION_CHECK_TEMPLATE` to prompts
- [ ] Add `_check_saturation()` method to DataCleaner
- [ ] Add `early_termination`, `saturation_check_interval` params
- [ ] Tests for saturation detection

**Success Criteria:**
- [ ] Saturation check runs every N chunks when enabled
- [ ] Processing stops if LLM says `saturated=true`
- [ ] 3+ tests pass

**Complexity:** Low

**Dependencies:** Phase 4

---

## Execution Strategy

Sequential phases (each depends on previous):

```
Phase 1: Tag Generation (~30 lines)
    ↓
Phase 2: IDF Grouping (~60 lines)
    ↓
Phase 3: Consolidation + Agency (~100 lines)
    ↓
Phase 4: Integration (~40 lines)
    ↓
Phase 5: Early Termination (~30 lines, optional)
```

## Line Budget

| Component | Current | Added | Target |
|-----------|---------|-------|--------|
| prompt.py | 131 | +40 | ~170 |
| optimizer.py | 0 | +150 | ~150 |
| response.py | 113 | +30 | ~145 |
| cleaner.py | 369 | +40 | ~410 |
| **Library Total** | 1847 | +260 | ~2100 |

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM generates invalid merged code | Medium | Medium | Validate with `ast.parse()`, retry on failure |
| Agency loop doesn't terminate | Low | High | Hard cap at `max_rounds=5` |
| Over-consolidation (merges unrelated) | Low | Medium | LLM reviews; can always keep separate |
| Tags inconsistent | Medium | Low | IDF handles naturally; fallback to name |

## Out of Scope

- Embedding-based similarity (too heavy)
- Cross-file function deduplication
- Interactive consolidation approval
- Undo/rollback of consolidation

---

## File Structure After Implementation

```
recursive_cleaner/
    optimizer.py    # NEW: Tags, grouping, consolidation
    prompt.py       # MODIFIED: Add tag instructions, consolidation template
    response.py     # MODIFIED: Add consolidation parsing
    cleaner.py      # MODIFIED: Add optimize params, call optimizer
    ...

tests/
    test_optimizer.py  # NEW: 30+ tests for optimization
    ...
```
