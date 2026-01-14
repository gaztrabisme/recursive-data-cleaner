# Recursive Data Cleaner

A Python library that uses LLMs to incrementally build data cleaning solutions for massive datasets. The system processes data in chunks, identifies quality issues, generates Python functions to solve them one at a time, and maintains awareness of existing solutions through docstring feedback loops.

## Features

- **Chunked Processing**: Handles large files that exceed LLM context windows (JSONL, CSV, JSON, text)
- **Incremental Function Generation**: Creates one cleaning function per iteration, building up a complete solution
- **Docstring Registry**: Feeds generated function docstrings back into prompts to avoid duplicate work
- **AST Validation**: Validates all generated Python code before output
- **Duplicate Detection**: Automatically skips duplicate function names
- **Error Recovery**: Retries with error feedback on parse failures
- **Backend Agnostic**: Works with any LLM that implements the simple `generate(prompt) -> str` interface

### v0.2.0 Features

- **Runtime Validation**: Tests generated functions on sample data before accepting them
- **Schema Inference**: Detects data schema and includes it in prompts for better LLM context
- **Progress Callbacks**: Optional callbacks for real-time progress updates
- **Incremental Saves**: Save state after each chunk, resume on interruption

## Installation

```bash
pip install -e .
```

For MLX backend (Apple Silicon):
```bash
pip install mlx-lm
```

## Quick Start

```python
from recursive_cleaner import DataCleaner
from backends import MLXBackend

# Initialize LLM backend
backend = MLXBackend(
    model_path="lmstudio-community/Qwen3-Next-80B-A3B-Instruct-MLX-4bit",
    max_tokens=4096,
    temperature=0.7,
)

# Create cleaner
cleaner = DataCleaner(
    llm_backend=backend,
    file_path="messy_data.jsonl",
    chunk_size=50,
    instructions="""
    CRM export data that needs:
    - Phone numbers normalized to E.164 format
    - Fix typos in 'status' field (valid: active, pending, churned)
    - All dates to ISO 8601
    """,
    max_iterations=5,
    # v0.2.0 options
    on_progress=lambda e: print(f"{e['type']}: chunk {e['chunk_index']}"),
    state_file="cleaning_state.json",  # Enable resume on interrupt
)

# Run and generate cleaning_functions.py
cleaner.run()

# Or resume from a previous run
# cleaner = DataCleaner.resume("cleaning_state.json", backend)
# cleaner.run()
```

## Output

The cleaner generates a `cleaning_functions.py` file containing:

1. Individual cleaning functions with docstrings
2. A `clean_data()` entrypoint that chains all functions

```python
# Generated output example
from cleaning_functions import clean_data

# Apply to your data
cleaned_record = clean_data({"phone": "555-1234", "status": "actve"})
```

## Custom LLM Backend

Implement the `LLMBackend` protocol:

```python
from recursive_cleaner.types import LLMBackend

class MyBackend:
    def generate(self, prompt: str) -> str:
        # Call your LLM here
        return response
```

## Architecture

```
recursive_cleaner/
├── __init__.py      # Public exports
├── cleaner.py       # Main DataCleaner class
├── context.py       # Docstring registry with FIFO eviction
├── errors.py        # Exception classes
├── output.py        # Function file generation
├── parsers.py       # File chunking (JSONL, CSV, JSON, text)
├── prompt.py        # LLM prompt template
├── response.py      # XML/markdown response parsing
├── schema.py        # Schema inference (v0.2.0)
├── types.py         # LLMBackend protocol
└── validation.py    # Runtime validation (v0.2.0)
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `chunk_size` | 50 | Items per chunk for JSONL/CSV/JSON |
| `max_iterations` | 5 | Max iterations per chunk |
| `context_budget` | 8000 | Max characters for docstring context |
| `validate_runtime` | True | Test functions on sample data before accepting |
| `schema_sample_size` | 10 | Records to sample for schema inference |
| `on_progress` | None | Callback for progress events |
| `state_file` | None | Path to save/resume state (enables incremental saves) |

## Testing

```bash
pytest tests/ -v
```

127 tests covering:
- File parsing (JSONL, CSV, JSON, text)
- Response parsing (XML, markdown code blocks)
- Context management (FIFO eviction)
- Error recovery (invalid XML, invalid Python)
- Integration tests (full pipeline)
- Runtime validation (v0.2.0)
- Schema inference (v0.2.0)
- Progress callbacks (v0.2.0)
- Incremental saves (v0.2.0)

## Test Cases

The `test_cases/` directory contains comprehensive datasets:

- **E-commerce**: Product catalog with price, date, SKU issues
- **Healthcare**: Patient records with phone, date, state formatting
- **Financial**: Transaction data with currency, time, status normalization

## Philosophy

- **Simplicity over extensibility**: ~977 lines that do one thing well
- **stdlib over dependencies**: Only `tenacity` for retries
- **Functions over classes**: Unless state genuinely helps
- **Delete over abstract**: No interfaces for single implementations
- **Retry over recover**: On error, retry with error message in prompt

## License

MIT
