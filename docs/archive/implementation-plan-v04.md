# Implementation Plan: Tier 2 Features (v0.4.0)

## Overview
Add four meaningful enhancements: validation holdout, dependency resolution, smart sampling, and quality metrics.

## Technology Stack
| Layer | Choice | Rationale |
|-------|--------|-----------|
| Dependency analysis | `ast` module | stdlib, no deps |
| Randomization | `hashlib` + `random` | Reproducible from file hash |
| Metrics | dataclass | Clean, typed |

---

## Phase 1: Validation Holdout

**Objective:** Split chunks for more rigorous validation.

**Deliverables:**
- [ ] Update `recursive_cleaner/validation.py` - add `split_holdout()` function
- [ ] Update `recursive_cleaner/cleaner.py` - add `holdout_ratio` param, use split
- [ ] `tests/test_holdout.py`

**Success Criteria:**
- [ ] `split_holdout(chunk, 0.2)` returns (generation_data, holdout_data)
- [ ] Structured mode: splits by records
- [ ] Text mode: splits at sentence boundary
- [ ] Empty holdout when `holdout_ratio=0`
- [ ] Function validation uses holdout data
- [ ] 10+ tests pass

**Complexity:** Low

**Dependencies:** None

---

## Phase 2: Dependency Resolution

**Objective:** Order generated functions by call dependencies.

**Deliverables:**
- [ ] Create `recursive_cleaner/dependencies.py` (~60 lines)
- [ ] Update `recursive_cleaner/output.py` - use resolved order
- [ ] `tests/test_dependencies.py`

**Success Criteria:**
- [ ] `detect_calls(code)` returns set of called function names
- [ ] `resolve_dependencies(functions)` returns sorted list
- [ ] Cycles don't crash (preserve order within cycle)
- [ ] `clean_data()` calls functions in resolved order
- [ ] 10+ tests pass

**Complexity:** Medium

**Dependencies:** None (can run parallel with Phase 1)

---

## Phase 3: Smart Sampling

**Objective:** Improve chunk diversity through sampling strategies.

**Deliverables:**
- [ ] Update `recursive_cleaner/parsers.py` - add sampling logic
- [ ] Update `recursive_cleaner/cleaner.py` - add params, pass to chunk_file
- [ ] `tests/test_sampling.py`

**Success Criteria:**
- [ ] `sampling_strategy="random"` shuffles records deterministically
- [ ] `sampling_strategy="stratified"` groups by field, samples proportionally
- [ ] Seed derived from file content hash (reproducible)
- [ ] Text mode only allows "sequential"
- [ ] 10+ tests pass

**Complexity:** Low-Medium

**Dependencies:** None (can run parallel with Phase 1, 2)

---

## Phase 4: Quality Metrics

**Objective:** Quantify cleaning effectiveness.

**Deliverables:**
- [ ] Create `recursive_cleaner/metrics.py` (~80 lines)
- [ ] Update `recursive_cleaner/cleaner.py` - add `track_metrics` param
- [ ] `tests/test_metrics.py`

**Success Criteria:**
- [ ] `QualityMetrics` dataclass captures nulls, empties, uniques
- [ ] `measure_quality(data)` works on list[dict]
- [ ] `compare_quality(before, after)` returns improvement dict
- [ ] `track_metrics=True` populates `metrics_before`/`metrics_after`
- [ ] `get_improvement_report()` returns comparison
- [ ] 10+ tests pass

**Complexity:** Medium

**Dependencies:** None (can run parallel)

---

## Risk Register
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Holdout too small | Low | Low | Minimum 1 record |
| Cycle in deps | Low | Medium | Preserve original order |
| Stratify field missing | Medium | Low | Skip stratification, warn |
| Large file metrics | Low | Medium | Sample-based measurement |

## Out of Scope
- Semantic similarity sampling
- Custom metrics functions
- Cross-chunk dependency detection

---

## Execution Strategy

All four phases are **independent** - can run in parallel.

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Phase 1          │  │ Phase 2          │  │ Phase 3          │  │ Phase 4          │
│ Validation       │  │ Dependency       │  │ Smart            │  │ Quality          │
│ Holdout          │  │ Resolution       │  │ Sampling         │  │ Metrics          │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │                     │
         └─────────────────────┴─────────────────────┴─────────────────────┘
                                         │
                                         ▼
                               ┌──────────────────┐
                               │ Integration &    │
                               │ Final Audit      │
                               └──────────────────┘
```

## Line Budget
| Component | Current | Added | Target |
|-----------|---------|-------|--------|
| validation.py | 99 | +30 | ~130 |
| dependencies.py | 0 | +60 | ~60 |
| parsers.py | 254 | +40 | ~295 |
| metrics.py | 0 | +80 | ~80 |
| cleaner.py | 311 | +30 | ~340 |
| **Total** | 1449 | +240 | ~1690 |
