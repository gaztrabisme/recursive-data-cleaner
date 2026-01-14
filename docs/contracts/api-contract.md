# API Contract - Tier 1 Features

## DataCleaner Constructor Changes

### Current (v0.1.0)
```python
DataCleaner(
    llm_backend: LLMBackend,
    file_path: str,
    chunk_size: int = 50,
    instructions: str = "",
    max_iterations: int = 5,
    context_budget: int = 8000,
)
```

### New (v0.2.0)
```python
DataCleaner(
    llm_backend: LLMBackend,
    file_path: str,
    chunk_size: int = 50,
    instructions: str = "",
    max_iterations: int = 5,
    context_budget: int = 8000,
    # NEW: Tier 1 features
    on_progress: Callable[[dict], None] | None = None,
    state_file: str | None = None,
    validate_runtime: bool = True,
    schema_sample_size: int = 10,
)
```

---

## Feature 1: Runtime Validation

### Module: `recursive_cleaner/validation.py`

```python
def validate_function(
    code: str,
    sample_data: list[dict],
    function_name: str,
) -> tuple[bool, str | None]:
    """
    Execute generated function on sample data to catch runtime errors.

    Args:
        code: The Python source code of the function
        sample_data: List of data records to test against
        function_name: Name of the function to call

    Returns:
        (True, None) if function executes without error
        (False, error_message) if function raises an exception
    """
```

### Integration Point
In `cleaner.py`, after `parse_response()` succeeds but before appending to `self.functions`:
1. Parse sample data from chunk (first 3-5 records)
2. Call `validate_function(result["code"], sample_data, result["name"])`
3. If fails, append error to `error_feedback` and continue loop
4. If passes, accept function

---

## Feature 2: Schema Inference

### Module: `recursive_cleaner/schema.py`

```python
def infer_schema(
    file_path: str,
    sample_size: int = 10,
) -> dict:
    """
    Infer data schema from first N records.

    Args:
        file_path: Path to data file
        sample_size: Number of records to sample

    Returns:
        {
            "fields": ["field1", "field2", ...],
            "types": {"field1": "str", "field2": "int", ...},
            "samples": {"field1": ["value1", "value2"], ...},
            "nullable": {"field1": False, "field2": True, ...}
        }
    """

def format_schema_for_prompt(schema: dict) -> str:
    """
    Format schema dict as human-readable string for prompt injection.

    Returns string like:
    Fields detected:
    - field1 (str): "sample1", "sample2", "sample3"
    - field2 (int, nullable): 123, 456, null
    """
```

### Integration Point
In `cleaner.py`, during `run()`:
1. Call `infer_schema(self.file_path, self.schema_sample_size)` once at start
2. Pass formatted schema to `build_prompt()` as new parameter

In `prompt.py`:
1. Add `schema: str = ""` parameter to `build_prompt()`
2. Insert `=== DATA SCHEMA ===\n{schema}` section before chunk

---

## Feature 3: Progress Callbacks

### Callback Event Types

```python
# Event structure
{
    "type": str,           # Event type (see below)
    "chunk_index": int,    # Current chunk (0-indexed)
    "total_chunks": int,   # Total number of chunks
    "iteration": int,      # Current iteration within chunk (optional)
    "function_name": str,  # Generated function name (optional)
    "status": str,         # Additional status info (optional)
}

# Event types:
# "chunk_start"       - Starting to process a chunk
# "iteration"         - Starting an iteration within chunk
# "function_generated"- Successfully generated a function
# "validation_failed" - Function failed runtime validation (new!)
# "chunk_done"        - Finished processing a chunk
# "complete"          - All processing finished
```

### Integration Point
In `cleaner.py`:
1. Store callback in `self.on_progress`
2. Add helper `_emit(event_type, **kwargs)` that safely calls callback
3. Call `_emit()` at appropriate points in `run()` and `_process_chunk()`

---

## Feature 4: Incremental Saves

### State File Format (JSON)

```json
{
    "version": "0.2.0",
    "file_path": "/path/to/data.jsonl",
    "instructions": "User instructions...",
    "chunk_size": 50,
    "last_completed_chunk": 3,
    "total_chunks": 10,
    "functions": [
        {
            "name": "normalize_phone",
            "docstring": "Normalizes phone numbers...",
            "code": "def normalize_phone(data): ..."
        }
    ],
    "timestamp": "2025-01-14T12:00:00Z"
}
```

### New Methods

```python
@classmethod
def resume(cls, state_file: str, llm_backend: LLMBackend) -> "DataCleaner":
    """
    Resume processing from a saved state file.

    Args:
        state_file: Path to state JSON file
        llm_backend: LLM backend to use (not saved in state)

    Returns:
        DataCleaner instance ready to continue processing

    Raises:
        FileNotFoundError: If state file doesn't exist
        ValueError: If state file is invalid
    """
```

### Integration Point
In `cleaner.py`:
1. Add `state_file` parameter to `__init__`
2. After each chunk completes in `_process_chunk()`, save state
3. In `run()`, if `state_file` exists, load and skip completed chunks
4. Add `resume()` classmethod for explicit resume

---

## Backwards Compatibility

All new parameters have defaults that preserve v0.1.0 behavior:
- `on_progress=None` - No callbacks (silent operation)
- `state_file=None` - No state persistence
- `validate_runtime=True` - NEW: Enabled by default (breaking change, but beneficial)
- `schema_sample_size=10` - Schema inference enabled by default

The only behavioral change is `validate_runtime=True` which adds safety, not removes it.
