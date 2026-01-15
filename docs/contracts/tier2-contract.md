# Tier 2 API Contract

## Overview
Four features that enhance validation, ordering, sampling, and metrics.

---

## Feature 1: Validation Holdout

### API Changes

```python
class DataCleaner:
    def __init__(
        self,
        ...,
        holdout_ratio: float = 0.2,  # NEW: 0.0-0.5, default 0.2
    )
```

### Behavior
- When `validate_runtime=True` AND `holdout_ratio > 0`:
  - Split chunk data: first `(1-holdout_ratio)` for generation, last `holdout_ratio` for testing
  - Generated functions tested on holdout portion before acceptance
  - If function fails on holdout, retry with error feedback
- When `holdout_ratio=0`: Current behavior (test on sample from generation data)

### Constraints
- Only applies to structured mode (JSONL/CSV/JSON)
- Text mode: holdout by sentences (split at sentence boundary)
- Minimum holdout: 1 record/sentence

---

## Feature 2: Dependency Resolution

### API Changes

```python
# New module: recursive_cleaner/dependencies.py

def resolve_dependencies(functions: list[dict]) -> list[dict]:
    """
    Reorder functions based on call dependencies.

    Args:
        functions: List of {name, docstring, code} dicts

    Returns:
        Topologically sorted list (callees before callers)
    """
```

### Behavior
- Uses `ast` to detect function calls within each function
- Builds dependency graph
- Topological sort ensures dependencies run first
- Handles cycles by preserving original order for cycle members

### Changes to output.py
- Call `resolve_dependencies()` before writing `clean_data()`
- Generated call order reflects resolved dependencies

---

## Feature 3: Smart Sampling

### API Changes

```python
class DataCleaner:
    def __init__(
        self,
        ...,
        sampling_strategy: Literal["sequential", "random", "stratified"] = "sequential",  # NEW
        stratify_field: str | None = None,  # NEW: field name for stratified sampling
    )
```

### Behavior
- `"sequential"`: Current behavior - process chunks in order
- `"random"`: Shuffle all records before chunking (seed from file hash for reproducibility)
- `"stratified"`: Group by `stratify_field`, sample proportionally from each group

### Constraints
- Only applies to structured mode
- Text mode: only `"sequential"` supported
- Stratified requires `stratify_field` to be set

---

## Feature 4: Quality Metrics

### API Changes

```python
# New module: recursive_cleaner/metrics.py

@dataclass
class QualityMetrics:
    null_count: int
    empty_string_count: int
    unique_values: dict[str, int]  # field -> count
    total_records: int
    timestamp: str

def measure_quality(data: list[dict]) -> QualityMetrics:
    """Measure quality metrics for a dataset."""

def compare_quality(before: QualityMetrics, after: QualityMetrics) -> dict:
    """Compare before/after metrics, return improvement percentages."""
```

### Integration with DataCleaner
```python
class DataCleaner:
    def __init__(
        self,
        ...,
        track_metrics: bool = False,  # NEW
    )

    # New attributes
    metrics_before: QualityMetrics | None
    metrics_after: QualityMetrics | None

    def get_improvement_report(self) -> dict | None:
        """Return comparison of before/after metrics."""
```

### Behavior
- When `track_metrics=True`:
  - Measure quality before processing starts
  - Measure quality after all functions generated
  - Store in `metrics_before` and `metrics_after`
- `get_improvement_report()` returns comparison dict

### Constraints
- Only meaningful for structured mode
- Text mode: track character count, whitespace ratio only

---

## Success Criteria

### Phase 1: Validation Holdout
- [ ] `holdout_ratio` parameter added to DataCleaner
- [ ] Chunk splitting works correctly for structured data
- [ ] Functions tested on holdout before acceptance
- [ ] Tests cover edge cases (small chunks, exact splits)
- [ ] 10+ new tests

### Phase 2: Dependency Resolution
- [ ] `dependencies.py` module created
- [ ] AST-based call detection works
- [ ] Topological sort implemented
- [ ] Cycles handled gracefully
- [ ] output.py uses resolved order
- [ ] 10+ new tests

### Phase 3: Smart Sampling
- [ ] `sampling_strategy` and `stratify_field` parameters added
- [ ] Random sampling with reproducible seed
- [ ] Stratified sampling works for categorical fields
- [ ] Text mode rejects non-sequential strategies
- [ ] 10+ new tests

### Phase 4: Quality Metrics
- [ ] `metrics.py` module created
- [ ] QualityMetrics dataclass defined
- [ ] `track_metrics` parameter added
- [ ] Before/after comparison works
- [ ] 10+ new tests

### Overall
- [ ] All 187+ existing tests pass
- [ ] 40+ new tests added
- [ ] Total lines < 1700
