# Data Schema Contract - Tier 1 Features

## Internal Data Structures

### Function Registry Entry (existing)
```python
{
    "name": str,      # Function name (e.g., "normalize_phone")
    "docstring": str, # Function docstring
    "code": str,      # Full Python source code
}
```

### Inferred Schema Structure (new)
```python
{
    "fields": list[str],              # Field names in order
    "types": dict[str, str],          # field -> inferred type
    "samples": dict[str, list[Any]],  # field -> sample values (up to 3)
    "nullable": dict[str, bool],      # field -> whether nulls were seen
}
```

### State File Structure (new)
```python
{
    "version": str,           # "0.2.0"
    "file_path": str,         # Original file path
    "instructions": str,      # User instructions
    "chunk_size": int,        # Chunk size setting
    "last_completed_chunk": int,  # Index of last completed chunk
    "total_chunks": int,      # Total chunks in file
    "functions": list[dict],  # List of function registry entries
    "timestamp": str,         # ISO 8601 timestamp
}
```

### Progress Event Structure (new)
```python
{
    "type": str,              # Event type enum
    "chunk_index": int,       # 0-indexed
    "total_chunks": int,      # Total count
    "iteration": int | None,  # Iteration within chunk
    "function_name": str | None,  # Generated function name
    "status": str | None,     # Additional info
}
```

---

## Type Inference Rules

When inferring types from sample data:

| Python Type | Inferred As | Examples |
|-------------|-------------|----------|
| `str` | `"str"` | "hello", "123-456" |
| `int` | `"int"` | 42, -1, 0 |
| `float` | `"float"` | 3.14, -0.5 |
| `bool` | `"bool"` | True, False |
| `None` | (marks nullable) | None, null |
| `list` | `"list"` | [1, 2, 3] |
| `dict` | `"dict"` | {"a": 1} |

Mixed types in same field → `"mixed"` with note of observed types.

---

## Validation Rules

### Runtime Validation
- Function must not raise any exception when called with sample data
- Sample data = first 3 records from current chunk
- Each record tested individually: `func(record)` must not raise
- Return value is not checked (only that it doesn't crash)

### State File Validation
- Must be valid JSON
- Must have `version` field matching current version
- Must have `file_path` matching current file (or user confirms override)
- `functions` must be list of valid function entries
- `last_completed_chunk` must be >= 0 and < `total_chunks`

---

## File Format Support

### Schema Inference Support

| Format | How Schema is Extracted |
|--------|------------------------|
| JSONL | Parse first N lines, union all keys |
| CSV | Headers become fields, infer types from rows |
| JSON (array) | Union keys from first N items |
| JSON (object) | Keys become fields |
| Text | Not supported (returns empty schema) |

### State Persistence Support

All formats supported - state captures chunking results, not file format specifics.
