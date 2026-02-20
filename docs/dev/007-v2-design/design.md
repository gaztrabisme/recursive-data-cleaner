# v2.0 Design: Distribution-Aware Cleaning

**Date**: 2026-02-20
**Mode**: Design
**Status**: Implemented (session 008)
**Philosophy**: Gradient descent towards the lowest energy point by the path of least resistance

---

## The Problem

The pipeline processes 20 records at a time. The LLM can't know that "Electronics" appears 37 times and "ELECTRONICS" 12 times — it only sees whatever's in the chunk. This causes:

1. **Can't determine canonical forms** — Is "Electronics" or "ELECTRONICS" the right category?
2. **Can't gauge issue severity** — Is `acitve` a one-off typo or 8% of the dataset?
3. **Can't prioritize** — Which issues affect the most records?

Evidence from eval: category_case is the hardest issue type (only 1/7 models solved it in v1.0.3). The model needs global context to know the canonical form.

## The Solution

**One pre-pass. One new string in the prompt. That's it.**

Scan the full dataset before chunking, compute per-field value frequency tables, inject them as a new prompt section. No architectural changes, no new LLM interactions, no new pipeline phases.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Load dataset │ ──► │ Count values │ ──► │ Format stats │
│ (reuse       │     │ per field    │     │ as text      │
│  existing)   │     │              │     │              │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                                                  ▼
                                          ┌──────────────┐
                                          │ Inject into  │
                                          │ every prompt │
                                          └──────────────┘
```

## What Gets Computed

For each field, compute value frequency counts. Split behavior by cardinality:

**Low cardinality (≤ 50 unique values)** — show full value counts:
```
status (100 values, 0 null):
  'active': 48 (48%)
  'pending': 16 (16%)
  'churned': 12 (12%)
  'actve': 8 (8%)       ← LLM can see this is a typo of 'active'
  'pendng': 6 (6%)
  'acitve': 4 (4%)
  'chruned': 4 (4%)
  'Active': 2 (2%)

category (100 values, 0 null):
  'Electronics': 37 (37%)    ← LLM can see Title Case is canonical
  'Clothing': 32 (32%)
  'Home & Garden': 16 (16%)
  'ELECTRONICS': 8 (8%)      ← These are the variants to normalize
  'electronics': 4 (4%)
  'CLOTHING': 3 (3%)
```

**High cardinality (> 50 unique values)** — summary only:
```
name: 98 unique values across 100 records
description: 85 unique values across 100 records
```

The LLM doesn't need a frequency table for names — each name is unique. But it DOES need the table for status and category.

## What Gets Injected

New prompt section between schema and data chunk:

```
=== FIELD VALUE DISTRIBUTIONS ===
Value frequencies across the FULL dataset (not just this chunk).
Use these to determine canonical forms and identify typos/variants.

status (100 values, 0 null):
  'active': 48 (48%)
  'pending': 16 (16%)
  ...

category (100 values, 0 null):
  'Electronics': 37 (37%)
  ...

name: 98 unique values (high cardinality, not shown)
description: 85 unique values (high cardinality, not shown)
```

## What Changes

### New file: `recursive_cleaner/stats.py` (~80 lines)

```python
from collections import Counter
from .metrics import load_structured_data

def compute_field_stats(file_path: str, max_cardinality: int = 50) -> dict:
    """One-pass value frequency computation."""
    data = load_structured_data(file_path)
    if not data:
        return {}

    fields = list(dict.fromkeys(k for r in data for k in r.keys()))
    stats = {}

    for field in fields:
        values = [r.get(field) for r in data if field in r]
        non_null = [v for v in values if v is not None]
        str_values = [str(v) for v in non_null]
        unique_count = len(set(str_values))

        if unique_count <= max_cardinality:
            counts = Counter(str_values).most_common(20)
            stats[field] = {
                "type": "categorical",
                "value_counts": counts,
                "total": len(values),
                "null_count": len(values) - len(non_null),
            }
        else:
            stats[field] = {
                "type": "high_cardinality",
                "unique": unique_count,
                "total": len(values),
            }

    return stats


def format_stats_for_prompt(stats: dict) -> str:
    """Format as human-readable text for prompt injection."""
    if not stats:
        return ""

    lines = [
        "Value frequencies across the FULL dataset (not just this chunk).",
        "Use these to determine canonical forms and identify typos/variants.",
    ]

    for field, info in stats.items():
        if info["type"] == "categorical":
            null_str = f", {info['null_count']} null" if info["null_count"] else ""
            lines.append(f"\n{field} ({info['total']} values{null_str}):")
            for value, count in info["value_counts"]:
                pct = count / info["total"] * 100
                lines.append(f"  {value!r}: {count} ({pct:.0f}%)")
        else:
            lines.append(f"\n{field}: {info['unique']} unique values (high cardinality)")

    return "\n".join(lines)
```

### Modified: `recursive_cleaner/prompt.py` (~5 lines)

Add `distributions` parameter to `build_prompt()`:

```python
def build_prompt(
    instructions: str,
    context: str,
    chunk: str,
    schema: str = "",
    distributions: str = "",   # NEW
    mode: Literal["structured", "text"] = "structured",
) -> str:
```

Inject into structured template:

```python
schema_section = f"\n=== DATA SCHEMA ===\n{schema}\n\n" if schema else "\n"
dist_section = f"=== FIELD VALUE DISTRIBUTIONS ===\n{distributions}\n\n" if distributions else ""
schema_section = schema_section + dist_section  # Append to existing section
```

### Modified: `recursive_cleaner/cleaner.py` (~10 lines)

In constructor (after `self._schema_str`):
```python
self._distributions_str: str = ""
```

In `run()` (after schema inference, line 377):
```python
from .stats import compute_field_stats, format_stats_for_prompt
stats = compute_field_stats(self.file_path)
self._distributions_str = format_stats_for_prompt(stats)
```

In `_build_prompt_for_chunk()` (wherever `build_prompt` is called):
```python
prompt = build_prompt(
    ...,
    distributions=self._distributions_str,
)
```

### New: `tests/test_stats.py` (~8-10 tests)

- `test_categorical_field_counts` — low cardinality field gets value counts
- `test_high_cardinality_field` — high cardinality gets summary only
- `test_null_handling` — null values counted separately
- `test_empty_dataset` — returns empty dict
- `test_format_for_prompt` — output is human-readable string
- `test_list_field_stringified` — list values serialized to string
- `test_cardinality_threshold` — `max_cardinality` parameter works
- `test_mixed_types` — fields with int/str/None all handled

## What Does NOT Change

- **No new pipeline phase** — stats computed alongside existing schema inference
- **No new LLM interactions** — stats are computed locally, not by the LLM
- **No new dependencies** — stdlib only (Counter from collections)
- **No changes to parsers, validation, output, response parsing**
- **Backward compatible** — `distributions=""` default means existing behavior unchanged
- **Text mode unaffected** — distributions only for structured mode

## What We Explicitly Defer

| Feature | Why Not Now |
|---------|------------|
| Compare mode (before/after diff) | Separate feature, not distribution-dependent |
| DataCleanBench | Separate benchmarking project |
| Format pattern detection (regex classification) | Value counts are sufficient; the LLM does the pattern recognition |
| Streaming stats for huge files | Premature — `load_structured_data()` already loads full file for metrics |
| Distribution-aware test case generation | Let's see if prompt injection alone works first |

## Projected Impact

The main target is **category_case** — the issue type where only 1/7 models generated a function in v1.0.3. With value distributions in the prompt, the LLM will see:

```
category (100 values, 0 null):
  'Electronics': 37 (37%)
  'Clothing': 32 (32%)
  'Home & Garden': 16 (16%)
  'ELECTRONICS': 8 (8%)
  'electronics': 4 (4%)
  'eLECTRONICS': 4 (4%)
```

This makes the cleaning task obvious: normalize to the most frequent variant (Title Case).

Secondary targets:
- **enum_typo**: LLM sees `'acitve': 4 (4%)` next to `'active': 48 (48%)` — typo is undeniable
- **weight_unit**: If we format weight values as categorical, LLM sees both kg/lbs variants and their frequencies

**Conservative estimate**: +5 category_case assertions for Coder-Next (3/8 → 8/8), keeping other scores stable.

## Verification Plan

1. Unit tests for `stats.py` — all 8-10 pass
2. Existing 698 tests still pass (no regressions)
3. Re-run 30B-A3B eval — score should remain ≥ 94.7% (no regression)
4. Re-run Coder-Next eval — category_case should improve from 3/8

## Summary

| Metric | Value |
|--------|-------|
| New code | ~80 lines (`stats.py`) |
| Modified code | ~15 lines across 2 files |
| New tests | ~8-10 |
| Files touched | 3 modified + 1 new |
| Dependencies | None |
| Backward compatible | Yes |
| Estimated build time | 1 session |
