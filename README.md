# Recursive Data Cleaner

LLM-powered incremental data cleaning for massive datasets. Process files in chunks, identify quality issues, and automatically generate Python cleaning functions.

## How It Works

1. **Chunk** your data (JSONL, CSV, JSON, or text)
2. **Analyze** each chunk with an LLM to identify issues
3. **Generate** one cleaning function per issue
4. **Validate** functions on holdout data before accepting
5. **Output** a ready-to-use `cleaning_functions.py`

The system maintains a "docstring registry" - feeding generated function descriptions back into prompts so the LLM knows what's already solved and avoids duplicate work.

## Installation

```bash
pip install -e .
```

For Apple Silicon (MLX backend):
```bash
pip install -e ".[mlx]"
```

## Quick Start

```python
from recursive_cleaner import DataCleaner
from backends import MLXBackend

# Any LLM with generate(prompt) -> str works
llm = MLXBackend(model_path="your-model")

cleaner = DataCleaner(
    llm_backend=llm,
    file_path="messy_data.jsonl",
    chunk_size=50,
    instructions="""
    - Normalize phone numbers to E.164
    - Fix typos in status field (valid: active, pending, churned)
    - Convert dates to ISO 8601
    """,
)

cleaner.run()  # Generates cleaning_functions.py
```

## Features

### Core
- **Chunked Processing**: Handle files larger than LLM context windows
- **Incremental Generation**: One function per issue, building up a complete solution
- **Docstring Registry**: Automatic context management with FIFO eviction
- **AST Validation**: All generated code validated before output
- **Error Recovery**: Retries with error feedback on parse failures

### Data Quality (v0.4.0+)
- **Holdout Validation**: Test functions on unseen 20% of each chunk
- **Sampling Strategies**: Sequential, random, or stratified sampling
- **Quality Metrics**: Before/after comparison with improvement reports
- **Dependency Resolution**: Topological sort for correct function ordering

### Optimization (v0.5.0+)
- **Two-Pass Consolidation**: Merge redundant functions after generation
- **Early Termination**: Stop when LLM detects pattern saturation
- **LLM Agency**: Model decides chunk cleanliness and saturation

### Security (v0.5.1+)
- **Dangerous Code Detection**: AST-based detection of exec, eval, subprocess, network calls

### Observability (v0.6.0)
- **Latency Metrics**: Track min/max/avg/total LLM call times
- **Import Consolidation**: Deduplicate and merge imports in output
- **Cleaning Reports**: Markdown summary with functions, timing, quality delta
- **Dry-Run Mode**: Analyze data without generating functions

## Configuration

```python
cleaner = DataCleaner(
    # Required
    llm_backend=llm,
    file_path="data.jsonl",

    # Chunking
    chunk_size=50,              # Items per chunk (or chars for text mode)
    max_iterations=5,           # Max iterations per chunk
    context_budget=8000,        # Max chars for docstring context

    # Validation
    validate_runtime=True,      # Test functions before accepting
    schema_sample_size=10,      # Records for schema inference
    holdout_ratio=0.2,          # Fraction held out for validation

    # Sampling
    sampling_strategy="stratified",  # "sequential", "random", "stratified"
    stratify_field="status",         # Field for stratified sampling

    # Optimization
    optimize=True,              # Consolidate redundant functions
    early_termination=True,     # Stop when patterns saturate
    track_metrics=True,         # Measure before/after quality

    # Observability
    report_path="report.md",    # Markdown report output (None to disable)
    dry_run=False,              # Analyze without generating functions

    # Progress & State
    on_progress=callback,       # Progress event callback
    state_file="state.json",    # Enable resume on interrupt
)
```

## Progress Events

```python
def on_progress(event):
    match event["type"]:
        case "chunk_start":
            print(f"Chunk {event['chunk_index']}/{event['total_chunks']}")
        case "llm_call":
            print(f"LLM latency: {event['latency_ms']}ms")
        case "function_generated":
            print(f"Generated: {event['function_name']}")
        case "issues_detected":  # dry-run mode
            print(f"Found {len(event['issues'])} issues")
        case "complete":
            stats = event["latency_stats"]
            print(f"Done! Avg latency: {stats['avg_ms']}ms")
```

## Output

The cleaner generates `cleaning_functions.py`:

```python
# Auto-generated cleaning functions
import re

def normalize_phone_numbers(data):
    """Normalize phone numbers to E.164 format."""
    # ... implementation ...

def fix_status_typos(data):
    """Fix typos in status field."""
    # ... implementation ...

def clean_data(data):
    """Apply all cleaning functions in order."""
    data = normalize_phone_numbers(data)
    data = fix_status_typos(data)
    return data
```

## Custom LLM Backend

Implement the simple protocol:

```python
class MyBackend:
    def generate(self, prompt: str) -> str:
        # Call your LLM (OpenAI, Anthropic, local, etc.)
        return response
```

## Text Mode

For plain text files (PDFs, documents):

```python
cleaner = DataCleaner(
    llm_backend=llm,
    file_path="document.txt",
    chunk_size=4000,  # Characters, not items
    instructions="Fix OCR errors, normalize whitespace",
)
```

Text mode uses sentence-aware chunking to avoid splitting mid-sentence.

## Resume on Interrupt

```python
# Start with state file
cleaner = DataCleaner(
    llm_backend=llm,
    file_path="huge_file.jsonl",
    state_file="cleaning_state.json",
)
cleaner.run()

# If interrupted, resume later:
cleaner = DataCleaner.resume("cleaning_state.json", llm)
cleaner.run()
```

## Architecture

```
recursive_cleaner/
├── cleaner.py       # Main DataCleaner class (~580 lines)
├── context.py       # Docstring registry with FIFO eviction
├── dependencies.py  # Topological sort for function ordering
├── metrics.py       # Quality metrics before/after
├── optimizer.py     # Two-pass consolidation with LLM agency
├── output.py        # Function file generation + import consolidation
├── parsers.py       # Chunking for JSONL/CSV/JSON/text + sampling
├── prompt.py        # LLM prompt templates
├── report.py        # Markdown report generation
├── response.py      # XML/markdown parsing + agency dataclasses
├── schema.py        # Schema inference
├── validation.py    # Runtime validation + holdout
└── vendor/
    └── chunker.py   # Vendored sentence-aware chunker
```

## Testing

```bash
pytest tests/ -v
```

392 tests covering all features. Test datasets in `test_cases/`:
- E-commerce product catalogs
- Healthcare patient records
- Financial transaction data

## Philosophy

- **Simplicity over extensibility**: ~3,000 lines that do one thing well
- **stdlib over dependencies**: Only `tenacity` required
- **Retry over recover**: On error, retry with error in prompt
- **Wu wei**: Let the LLM make decisions about data it understands

## Version History

| Version | Features |
|---------|----------|
| v0.6.0 | Latency metrics, import consolidation, cleaning report, dry-run mode |
| v0.5.1 | Dangerous code detection (AST-based security) |
| v0.5.0 | Two-pass optimization, early termination, LLM agency |
| v0.4.0 | Holdout validation, dependency resolution, sampling, quality metrics |
| v0.3.0 | Text mode with sentence-aware chunking |
| v0.2.0 | Runtime validation, schema inference, callbacks, incremental saves |
| v0.1.0 | Core pipeline, chunking, docstring registry |

## Acknowledgments

- Sentence-aware text chunking adapted from [Chonkie](https://github.com/chonkie-inc/chonkie) (MIT License)
- Development assisted by [Claude Code](https://claude.ai/claude-code)

## License

MIT
