# Two-Pass Optimization Contract

## Overview

Add a second pass that consolidates redundant functions after generation completes. LLM has agency to decide when consolidation is complete.

---

## Feature 1: Tagged Docstrings

### Prompt Modification

Generation prompt includes instruction for tags:

```
<docstring>
What the function does, edge cases handled.
Tags: tag1, tag2, tag3
</docstring>

RULES:
- Include 2-5 tags describing what the function handles
- Tags should be lowercase, single words
- Use domain terms (date, phone, email) and action terms (normalize, validate, fix)
```

### Docstring Format

```python
def normalize_phone_numbers(record):
    """
    Normalize phone numbers to E.164 format.
    Handles: +1-555-1234, (555) 123-4567, raw digits
    Tags: phone, normalize, format
    """
```

### Tag Extraction

```python
def extract_tags(docstring: str) -> set[str]:
    """Extract tags from docstring. Returns empty set if none."""
```

---

## Feature 2: IDF-Based Grouping

### API

```python
# New file: recursive_cleaner/optimizer.py

def group_by_salience(functions: list[dict]) -> dict[str, list[dict]]:
    """
    Group functions by most informative tag (highest IDF).

    Args:
        functions: List of {name, docstring, code} dicts

    Returns:
        Dict mapping primary tag to list of functions
    """
```

### Behavior

1. Extract tags from all function docstrings
2. Calculate IDF: `log(N / doc_freq[tag])` for each tag
3. Assign each function to its highest-IDF tag
4. Rebalance: merge groups < 2 functions, split groups > 40

### Fallback

Functions without tags: extract category from function name

```python
def _fallback_from_name(name: str) -> str:
    """Extract domain word from function name."""
    # "normalize_phone_format" → "phone"
```

---

## Feature 3: Consolidation with LLM Agency

### Consolidation Prompt

```xml
You are reviewing cleaning functions for consolidation.

=== FUNCTIONS TO REVIEW ===
{formatted_functions}

=== TASK ===
1. Identify functions that handle the SAME type of issue
2. Merge redundant functions into fewer, more general ones
3. Keep functions that are unique

=== OUTPUT FORMAT ===
<consolidation_result>
  <merged_functions>
    <function>
      <name>merged_function_name</name>
      <original_names>func1, func2, func3</original_names>
      <docstring>
      Combined description.
      Tags: tag1, tag2
      </docstring>
      <code>
```python
def merged_function_name(record):
    ...
```
      </code>
    </function>
  </merged_functions>

  <kept_unchanged>
    <function_name>unique_func1</function_name>
    <function_name>unique_func2</function_name>
  </kept_unchanged>

  <self_assessment>
    <complete>true|false</complete>
    <remaining_issues>
      Description of any remaining redundancy, or "none"
    </remaining_issues>
    <confidence>high|medium|low</confidence>
  </self_assessment>
</consolidation_result>
```

### Agency Loop

```python
def consolidate_with_agency(
    functions: list[dict],
    backend: LLMBackend,
    max_rounds: int = 5,
) -> list[dict]:
    """
    Consolidate functions until LLM reports complete.

    Stops when:
    - self_assessment.complete == true, OR
    - max_rounds reached (safety cap)
    """
```

### Assessment Dataclass

```python
@dataclass
class AgentAssessment:
    complete: bool
    remaining_issues: str
    confidence: Literal["high", "medium", "low"]
```

---

## Feature 4: Integration with DataCleaner

### New Parameters

```python
class DataCleaner:
    def __init__(
        self,
        ...,
        optimize: bool = False,  # Enable two-pass optimization
        optimize_threshold: int = 10,  # Min functions before optimizing
    )
```

### Behavior

When `optimize=True` and `len(functions) >= optimize_threshold`:
1. After all chunks processed, group functions by IDF
2. For each group, run consolidation with agency
3. Replace `self.functions` with consolidated result
4. Write optimized output

### Progress Callbacks

```python
# New event types
{"type": "optimize_start", "function_count": 47}
{"type": "optimize_group", "group": "date", "count": 12}
{"type": "optimize_round", "round": 1, "remaining_issues": "..."}
{"type": "optimize_complete", "original": 47, "final": 23}
```

---

## Feature 5: Early Termination (Bonus Agency Point)

### Saturation Detection

After every N chunks, assess if patterns are saturated:

```python
def _check_saturation(self) -> bool:
    """Ask LLM if we've seen enough variety."""
```

```xml
<saturation_check>
  <functions_generated>42</functions_generated>
  <recent_chunks_analyzed>10</recent_chunks_analyzed>
  <new_functions_from_recent>1</new_functions_from_recent>

  <assessment>
    <saturated>true|false</saturated>
    <reasoning>Last 10 chunks only produced 1 new function type</reasoning>
    <recommendation>stop|continue</recommendation>
  </assessment>
</saturation_check>
```

### Integration

```python
class DataCleaner:
    def __init__(
        self,
        ...,
        early_termination: bool = False,  # Enable saturation detection
        saturation_check_interval: int = 20,  # Check every N chunks
    )
```

---

## Success Criteria

### Phase 1: Tag Generation
- [ ] Prompt template updated with tag instruction
- [ ] `extract_tags()` function implemented
- [ ] Tags appear in generated docstrings
- [ ] 5+ tests

### Phase 2: IDF Grouping
- [ ] `group_by_salience()` implemented
- [ ] IDF calculation correct
- [ ] Rebalancing works (merge small, split large)
- [ ] Fallback for untagged functions
- [ ] 10+ tests

### Phase 3: Consolidation
- [ ] Consolidation prompt template created
- [ ] `consolidate_with_agency()` implemented
- [ ] Agency loop stops on `complete=true`
- [ ] Safety cap prevents infinite loops
- [ ] 10+ tests

### Phase 4: Integration
- [ ] `optimize` parameter added to DataCleaner
- [ ] Progress callbacks for optimization events
- [ ] End-to-end test with real data
- [ ] 5+ tests

### Phase 5: Early Termination (Optional)
- [ ] Saturation check implemented
- [ ] `early_termination` parameter added
- [ ] 3+ tests

### Overall
- [ ] All existing 271 tests pass
- [ ] 30+ new tests
- [ ] Total lines < 2100
